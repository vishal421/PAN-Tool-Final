import MigrationPage from '../../components/seo/MigrationPage'
import { ciscoContent } from '../../seo/content/cisco'

export default function CiscoMigrationPage({ onGetStarted }) {
  return <MigrationPage data={ciscoContent} onGetStarted={onGetStarted} />
}
