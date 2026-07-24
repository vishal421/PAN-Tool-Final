import MigrationPage from '../../components/seo/MigrationPage'
import { fortigateContent } from '../../seo/content/fortigate'

export default function FortigateMigrationPage({ onGetStarted }) {
  return <MigrationPage data={fortigateContent} onGetStarted={onGetStarted} />
}
