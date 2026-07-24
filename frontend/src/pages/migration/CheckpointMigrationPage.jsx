import MigrationPage from '../../components/seo/MigrationPage'
import { checkpointContent } from '../../seo/content/checkpoint'

export default function CheckpointMigrationPage({ onGetStarted }) {
  return <MigrationPage data={checkpointContent} onGetStarted={onGetStarted} />
}
