import MigrationPage from '../../components/seo/MigrationPage'
import { sophosContent } from '../../seo/content/sophos'

export default function SophosMigrationPage({ onGetStarted }) {
  return <MigrationPage data={sophosContent} onGetStarted={onGetStarted} />
}
