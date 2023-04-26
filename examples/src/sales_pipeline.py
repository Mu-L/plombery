from asyncio import sleep
from datetime import datetime
from dateutil import tz

from apscheduler.triggers.interval import IntervalTrigger
import numpy as np
import pandas as pd
from pydantic import BaseModel

from mario import register_pipeline, task, Trigger, get_logger


class InputParams(BaseModel):
    some_value: int


@task
async def get_sales_data(params: InputParams) -> pd.DataFrame:
    """
    Fetch raw sales data by store and SKU

    Latest 50 days worth of data are pulled from the e-commerce APIs.
    """

    logger = get_logger()

    logger.info("Pipeline called with some_value=%d", params.some_value)

    for i in range(10):
        await sleep(1 + np.random.random() / 2)
        logger.debug("Iteration %d", i)

    logger.warning("Nothing serious but you should fix this")

    data = pd.DataFrame(
        {
            "price": np.random.randint(1, 1000, 50),
            "store_id": np.random.randint(1, 10, 50),
            "date": datetime.today(),
            "sku": np.random.randint(1, 50, 50),
        }
    )

    if np.random.random() > 0.75:
        raise ValueError("I decided to fail :P")

    return data


@task
async def upload_to_s3(data: pd.DataFrame):
    pass


register_pipeline(
    id="sales_pipeline",
    description="""This is a very useless pipeline""",
    tasks=[get_sales_data, upload_to_s3],
    triggers=[
        Trigger(
            id="daily",
            name="Daily",
            description="Run the pipeline every day",
            params=InputParams(some_value=2),
            aps_trigger=IntervalTrigger(
                days=1,
                start_date=datetime(
                    2023, 1, 1, 22, 30, tzinfo=tz.gettz("Europe/Brussels")
                ),
            ),
        )
    ],
    params=InputParams,
)
