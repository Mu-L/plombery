import { Grid, Title } from '@tremor/react'

import PageLayout from '@/components/PageLayout'
import PipelinesList from '@/components/PipelinesList'
import RunsList from '@/components/RunsList'
import { useQuery } from '@tanstack/react-query'
import { listRuns } from '@/repository'

const HomePage: React.FC = () => {
  const runsQuery = useQuery(listRuns())

  if (runsQuery.isLoading) return <div>Loading...</div>

  if (runsQuery.isError) return <div>An error has occurred</div>

  return (
    <PageLayout
      header={
        <>
          <Title>Plombery</Title>
        </>
      }
    >
      <Grid numItemsMd={2} className="gap-6 mt-6">
        <PipelinesList />

        {runsQuery.isLoading ? (
          'Loading...'
        ) : runsQuery.isError ? (
          'Error loading runs'
        ) : (
          <RunsList runs={runsQuery.data} />
        )}
      </Grid>
    </PageLayout>
  )
}

export default HomePage
