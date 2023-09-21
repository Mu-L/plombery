from logging import getLogger
from typing import Optional

from fastapi import (
    Body,
    FastAPI,
    HTTPException,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware

from plombery.api.authentication import NeedsAuth, init_auth
from plombery.config import settings
from plombery.pipeline.pipeline import Pipeline, Trigger
from plombery.orchestrator import orchestrator, run_pipeline_now
from plombery.orchestrator.executor import get_pipeline_run_logs, get_pipeline_run_data
from plombery.database.repository import list_pipeline_runs, get_pipeline_run
from plombery.websocket import manager
from .middlewares import FRONTEND_FOLDER, SPAStaticFiles


logger = getLogger(__name__)

app = FastAPI()

api = FastAPI()
app.mount("/api", api)

init_auth(api)

origins = [
    settings.frontend_url,
]

# Help during develop so the app can be opened at localhost or 127.0.0.1
if settings.frontend_url.host == "localhost":
    origins.append(str(settings.frontend_url).replace("localhost", "127.0.0.1"))
elif settings.frontend_url.host == "127.0.0.1":
    origins.append(str(settings.frontend_url).replace("127.0.0.1", "localhost"))


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _populate_next_fire_time(pipeline: Pipeline) -> None:
    for trigger in pipeline.triggers:
        if not trigger.schedule:
            continue

        if job := orchestrator.get_job(pipeline.id, trigger.id):
            trigger.next_fire_time = job.next_run_time


@api.get(
    "/pipelines",
    response_model=None,
    tags=["Pipelines"],
)
def list_pipelines(user=NeedsAuth):
    pipelines = list(orchestrator.pipelines.values())

    for pipeline in pipelines:
        _populate_next_fire_time(pipeline)

    return jsonable_encoder(
        pipelines,
        custom_encoder=Trigger.Config.json_encoders,
    )


@api.get(
    "/pipelines/{pipeline_id}",
    response_model=None,
    tags=["Pipelines"],
)
def get_pipeline(pipeline_id: str, user=NeedsAuth):
    if not (pipeline := orchestrator.get_pipeline(pipeline_id)):
        raise HTTPException(404, f"The pipeline with ID {pipeline_id} doesn't exist")

    _populate_next_fire_time(pipeline)

    return jsonable_encoder(pipeline, custom_encoder=Trigger.Config.json_encoders)


@api.get(
    "/pipelines/{pipeline_id}/input-schema",
    tags=["Pipelines"],
)
def get_pipeline_input_schema(pipeline_id: str, user=NeedsAuth):
    if not (pipeline := orchestrator.get_pipeline(pipeline_id)):
        raise HTTPException(404, f"The pipeline with ID {pipeline_id} doesn't exist")

    return pipeline.params.schema() if pipeline.params else dict()


@api.get(
    "/runs",
    tags=["Runs"],
)
def list_runs(
    pipeline_id: Optional[str] = None, trigger_id: Optional[str] = None, user=NeedsAuth
):
    return list_pipeline_runs(pipeline_id=pipeline_id, trigger_id=trigger_id)


@api.get("/runs/{run_id}", tags=["Runs"])
def get_run(run_id: int, user=NeedsAuth):
    if not (pipeline_run := get_pipeline_run(run_id)):
        raise HTTPException(404, f"The pipeline run {run_id} doesn't exist")

    return pipeline_run


@api.get("/runs/{run_id}/logs", tags=["Runs"])
def get_logs(run_id: int, user=NeedsAuth):
    logs = get_pipeline_run_logs(run_id)
    return Response(content=logs, media_type="application/jsonl")


@api.get("/runs/{run_id}/data/{task}", tags=["Runs"])
def get_data(run_id: int, task: str, user=NeedsAuth):
    data = get_pipeline_run_data(run_id, task)

    if not data:
        raise HTTPException(status_code=404, detail="Task has no data")

    return data


@api.post("/pipelines/{pipeline_id}/run", tags=["Runs"])
async def run_pipeline(
    pipeline_id: str, params: Optional[dict] = Body(), user=NeedsAuth
):
    if not (pipeline := orchestrator.get_pipeline(pipeline_id)):
        raise HTTPException(404, f"The pipeline with ID {pipeline_id} doesn't exist")

    return await run_pipeline_now(pipeline, None, params)


@api.post("/pipelines/{pipeline_id}/triggers/{trigger_id}/run", tags=["Runs"])
async def run_trigger(pipeline_id: str, trigger_id: str, user=NeedsAuth):
    if not (pipeline := orchestrator.get_pipeline(pipeline_id)):
        raise HTTPException(404, f"The pipeline with ID {pipeline_id} doesn't exist")

    triggers = [trigger for trigger in pipeline.triggers if trigger.id == trigger_id]

    if len(triggers) == 0:
        raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found")

    trigger = triggers[0]

    return await run_pipeline_now(pipeline, trigger)


@api.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            await manager.handle_messages(websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


app.mount("/", SPAStaticFiles(directory=FRONTEND_FOLDER, html=True))
