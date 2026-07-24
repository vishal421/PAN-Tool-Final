export const bpaSeoContent = {
  key: 'bpa',
  path: '/palo-alto-bpa-report-generator',
  title: 'Palo Alto BPA Report Generator | Best Practice Assessment Tool',
  description:
    'Generate a Palo Alto Networks Best Practice Assessment (BPA) report for your NGFW or Panorama configuration in minutes. Free BPA report generator with instant severity breakdown and Excel export.',
  heroEyebrow: 'Palo Alto Networks · Best Practice Assessment',
  h1: 'Generate a Palo Alto BPA report in minutes, not a support ticket',
  heroSub:
    'Run an official Best Practice Assessment against your Palo Alto NGFW or Panorama configuration using Palo Alto\u2019s own BPA API \u2014 then turn the results into a clean, severity-ranked Excel workbook your team can actually act on.',
  intro: [
    'A Palo Alto Best Practice Assessment (BPA) compares your live firewall or Panorama configuration against Palo Alto Networks\u2019 own security hardening guidelines \u2014 things like weak authentication profiles, missing zone protection, permissive security rules, disabled threat prevention profiles, and dozens of other checks across every rulebase and object type.',
    'Getting that report has traditionally meant opening a case, waiting on an SE, or hand-rolling API calls against the SCM Posture Management API yourself. This BPA report generator does the API plumbing for you: authenticate with your own Palo Alto API credentials, upload your exported configuration, and poll for the finished report \u2014 all from one page.',
    'Once the raw BPA JSON comes back, most teams still have to manually sort hundreds of findings by severity before anyone can prioritize remediation. This tool converts that JSON straight into a formatted Excel report, with every check pre-classified as Critical, Medium, Informational, or Pass, and color-coded so a security or network team can triage it at a glance.',
  ],
  challenges: {
    heading: 'Why teams put off running a BPA',
    items: [
      { title: 'API auth is fiddly', body: 'Getting a working OAuth2 client_credentials token from Palo Alto\u2019s auth service, scoped to the right TSG ID, trips up most people on the first try.' },
      { title: 'Presigned upload URLs', body: 'The config upload step expects an exact, gzip-encoded PUT to a signed URL \u2014 get the headers or encoding wrong and the upload silently fails.' },
      { title: 'Raw JSON isn\u2019t a deliverable', body: 'A multi-megabyte nested JSON blob of check results isn\u2019t something you hand to a manager or attach to a change ticket \u2014 it needs to become a report first.' },
      { title: 'Hundreds of findings, no ranking', body: 'Without severity sorting, a genuinely critical misconfiguration can sit buried on page 40 next to routine informational notes.' },
    ],
  },
  workflow: {
    heading: 'How the BPA report generator works',
    steps: [
      { title: 'Authenticate', body: 'Enter your Palo Alto API Client ID, Client Secret, and TSG ID. The tool exchanges these for a short-lived access token via Palo Alto\u2019s own auth endpoint.' },
      { title: 'Upload your config', body: 'Choose NGFW or Panorama, then upload your exported configuration XML (or point to a URL). It\u2019s gzipped and pushed to Palo Alto\u2019s presigned upload URL for you.' },
      { title: 'Generate the BPA result', body: 'Poll Palo Alto\u2019s Posture Management API for the finished assessment. Typically ready within a minute or two of a successful upload.' },
      { title: 'Export a ranked Excel report', body: 'Convert the returned JSON into an Excel workbook with every finding classified Critical / Medium / Informational / Pass, plus a summary sheet with totals by severity.' },
    ],
  },
  benefits: [
    { title: 'No support ticket required', body: 'Run the same BPA that Palo Alto\u2019s own SEs use, on your own schedule, using your own API credentials \u2014 nothing to request or wait on.' },
    { title: 'Works for NGFW and Panorama', body: 'Assess a standalone firewall configuration or a full Panorama-managed device group in the same tool.' },
    { title: 'Severity-ranked, not just raw JSON', body: 'Every check is automatically bucketed by severity and color-coded, so Critical findings never get lost in a wall of Informational notes.' },
    { title: 'A real deliverable', body: 'The Excel export is something you can actually attach to a change record, a security review, or a compliance audit \u2014 not a JSON file nobody wants to open.' },
    { title: 'Nothing stored server-side', body: 'Your Client Secret and access token live only in your browser tab for the current session \u2014 never written to a database or logged.' },
    { title: 'Repeatable', body: 'Re-run the assessment after every major change window to track whether your hardening posture is improving or regressing over time.' },
  ],
  checklist: {
    heading: 'Before you run a BPA report',
    items: [
      { title: 'Have an API-enabled service account', body: 'You\u2019ll need a Palo Alto Networks API Client ID, Client Secret, and TSG ID with access to the Posture Management (BPA) API scope.' },
      { title: 'Export your configuration', body: 'Pull a full running (or candidate) configuration export in XML from your NGFW or Panorama \u2014 the same file format used for backups.' },
      { title: 'Confirm outbound HTTPS access', body: 'The device running this tool needs to reach auth.apps.paloaltonetworks.com and api.sase.paloaltonetworks.com.' },
      { title: 'Know who\u2019s reviewing the results', body: 'Decide upfront who owns triaging Critical findings \u2014 the Excel export is built to make that handoff quick.' },
    ],
  },
  faq: [
    { q: 'What is a Palo Alto BPA report?', a: 'A Best Practice Assessment (BPA) is Palo Alto Networks\u2019 own automated review of a firewall or Panorama configuration against their published security hardening best practices \u2014 covering things like authentication, decryption, threat prevention profiles, zone protection, and security rule hygiene.' },
    { q: 'Do I need a Palo Alto support contract to run a BPA?', a: 'You need an API-enabled service account (Client ID, Client Secret, TSG ID) with access to the Posture Management API, which is generally available as part of Palo Alto\u2019s Customer Support Portal / SCM access \u2014 check with your account team if you\u2019re unsure of your entitlement.' },
    { q: 'Does this tool store my Palo Alto API credentials?', a: 'No. Your Client Secret and the access token it produces exist only in your browser tab for the current session and are never written to a database, file, or log.' },
    { q: 'Can I assess a Panorama-managed configuration, not just a standalone firewall?', a: 'Yes \u2014 choose \u201cpanorama\u201d as the device type in Step 2 before uploading your Panorama configuration export.' },
    { q: 'What do the severity levels (Critical, Medium, Informational, Pass) mean?', a: 'They mirror Palo Alto\u2019s own check_type classification in the BPA API response: Critical and High-risk checks are surfaced as Critical, warning-level checks as Medium, advisory checks as Informational, and any check that passed is marked Pass.' },
    { q: 'How long does generating a BPA report take?', a: 'Uploading the configuration is near-instant; Palo Alto\u2019s backend typically finishes processing the assessment within one to a few minutes, depending on configuration size \u2014 you poll for status and it\u2019ll tell you when it\u2019s ready.' },
    { q: 'Can I convert a BPA report I already generated elsewhere into Excel?', a: 'Yes \u2014 the Excel export step accepts pasted JSON, an uploaded .json file, or a URL, not only a report generated in this same session.' },
  ],
  closing: {
    heading: 'Ready to see where your Palo Alto configuration actually stands?',
    body: 'Run a full Best Practice Assessment and walk away with a severity-ranked Excel report your team can act on today.',
  },
}
