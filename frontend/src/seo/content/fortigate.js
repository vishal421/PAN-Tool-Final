export const fortigateContent = {
  key: 'fortigate',
  vendorLabel: 'FortiGate',
  path: '/fortigate-to-palo-alto-migration',
  title: 'FortiGate to Palo Alto Migration Tool | Convert FortiOS to PAN-OS',
  description:
    'Convert FortiGate FortiOS configurations to Palo Alto PAN-OS automatically. Migrate address objects, VDOMs, security profiles, and policies with built-in validation.',
  heroEyebrow: 'FortiGate &rarr; Palo Alto Networks',
  h1: 'FortiGate to Palo Alto Migration, Without Rebuilding Every Policy by Hand',
  heroSub:
    'Convert FortiOS address objects, service definitions, VDOM-scoped policies, and security profiles into a validated Palo Alto PAN-OS configuration set — parsed deterministically, not scraped with regular expressions.',
  intro: [
    'Moving a firewall estate from FortiGate to Palo Alto Networks is one of the more common — and more error-prone — migrations network teams take on. FortiOS and PAN-OS model network security differently enough that a line-by-line manual conversion invites mistakes: a missed VDOM boundary, a security profile that silently disappears, or a policy that references an interface alias nobody documented. A firewall migration tool built specifically for this vendor pair removes the guesswork by parsing the source configuration into a structured model first, then generating PAN-OS CLI from that model.',
    'FortiGate configurations describe address objects, service objects, address groups, VDOMs, zones, interfaces, and firewall policies in a fairly dense CLI grammar full of "edit" and "set" blocks. Palo Alto PAN-OS uses a comparable but distinct object model — address objects and address groups, service objects and service groups, zones, virtual routers, and security rules — with its own syntax and its own rules about what must exist before something else can reference it. A firewall configuration converter has to understand both grammars, not just transliterate text.',
    'This matters most in security policy migration. FortiGate policies commonly reference multiple source and destination interfaces, apply UTM security profiles (antivirus, IPS, web filtering, application control) as named profile groups, and can rely on implicit VDOM context that never appears in a single policy line. Translating that into PAN-OS security rules means resolving each FortiGate zone to its PAN-OS equivalent, mapping security profiles to PAN-OS Security Profile Groups or individual profiles, and preserving rule order and intent — not just the raw text of each line.',
    'The tool on this page automates that translation end to end: import a FortiGate configuration export, review the parsed objects and policies in an editable grid, resolve interfaces and zones through a guided mapping step, and export a dependency-ordered PAN-OS CLI file that is ready to load. Nothing is uploaded to a third-party cloud service — parsing and generation run against your own imported file.',
    'For a network team managing more than a handful of policies, the real cost of a manual FortiGate to Palo Alto migration is not any single conversion mistake — it is the review cycle needed to catch them. Every retyped address object, every re-derived zone mapping, and every manually copied security profile is another place a change control review has to check by hand before a cutover window. An automated firewall configuration converter turns that review into a smaller, more targeted task: confirming a parsed model and a handful of explicit mapping decisions, instead of re-verifying every line of generated CLI against the original FortiOS configuration from scratch.',
    'FortiManager adds another wrinkle for teams centrally managing several FortiGate appliances. Policy packages, global objects, and per-device local objects can all contribute to what a single FortiGate actually enforces, and a device-level configuration backup does not always make that provenance obvious. When importing a FortiManager-administered device, it is worth confirming during review that every object referenced by a policy actually appears in the parsed inventory — an object that only existed at the FortiManager level and was never pushed down, or one that was overridden locally, is the kind of gap that is much cheaper to catch on the Objects tab than after a rule fails to load on the Palo Alto side.',
    'SD-WAN is increasingly part of what gets migrated alongside a straightforward firewall policy. FortiGate\'s SD-WAN implementation ties performance SLAs and link selection into the same policy evaluation as security rules, which has no direct one-to-one PAN-OS equivalent — Palo Alto handles path selection through its own SD-WAN subscription and separate policy constructs. A firewall migration tool cannot silently invent that mapping, so the parser instead surfaces FortiGate SD-WAN rules and health-check definitions as explicit, reviewable items rather than pretending they translate automatically, so a network architect can make a deliberate decision about how (or whether) to reproduce that behavior on the target platform.',
  ],
  challenges: {
    heading: 'Why FortiGate to Palo Alto migration goes wrong when it is done by hand',
    items: [
      {
        title: 'VDOMs do not map cleanly to PAN-OS virtual systems',
        body: 'FortiGate VDOMs partition a single physical appliance into logically separate firewalls, each with its own routing table, zones, and policies. PAN-OS models multi-tenancy differently through virtual systems and shared objects. A manual migration frequently collapses VDOM boundaries by accident, mixing objects that were supposed to stay isolated.',
      },
      {
        title: 'Security profiles get silently dropped',
        body: 'FortiGate policies attach UTM profiles — antivirus, IPS, web filtering, application control — directly to a rule. When engineers focus on getting the address and service objects right, profile attachments are the first thing to get missed, leaving a technically "working" PAN-OS rule with none of the original inspection applied.',
      },
      {
        title: 'Interface and zone naming diverges immediately',
        body: 'FortiGate uses physical and aggregate interface names like port1 or port12, often bound to a zone name defined elsewhere. PAN-OS expects interfaces bound to a zone and a virtual router at creation time. Without a mapping step, engineers end up guessing at zone equivalence rule by rule.',
      },
      {
        title: 'Object and group references break independently',
        body: 'FortiGate address groups and service groups can nest several layers deep. Renaming or skipping an object during manual retyping breaks every group and every policy downstream of it, and those broken references often surface only after import — during a maintenance window, not before it.',
      },
      {
        title: 'SD-WAN rules and FortiManager policy packages complicate scope',
        body: 'SD-WAN link-selection rules can influence which policy actually applies, and FortiManager-administered devices mix global, package-level, and per-device local objects. Working from a single device backup without accounting for that layering risks missing objects a policy silently depended on.',
      },
      {
        title: 'Implicit "deny all" behavior is easy to misread',
        body: 'FortiGate policies are evaluated top-down against an implicit final deny, similar in spirit to PAN-OS but not identical in how logging and default services are handled. Retyping rule order without preserving intent can quietly change what traffic is allowed by default.',
      },
      {
        title: 'Route-based and policy-based VPN references get tangled with firewall policy',
        body: 'FortiGate firewall policies frequently reference IPsec phase 1/phase 2 tunnel interfaces directly by name. Renaming or restructuring those tunnel interfaces during migration without updating every referencing policy leaves rules pointing at interfaces that no longer exist.',
      },
      {
        title: 'Central NAT and per-policy NAT are easy to mix up',
        body: 'FortiGate supports both a centralized NAT table and NAT settings embedded directly in individual firewall policies. A migration that only looks at one location can miss NAT behavior defined in the other, producing PAN-OS NAT rules that do not match production traffic flow.',
      },
    ],
  },
  workflow: {
    heading: 'How the FortiGate to Palo Alto conversion works',
    steps: [
      { title: 'Import the FortiGate export', body: 'Upload a FortiOS configuration file. The parser reads address objects, address groups, services, service groups, VDOMs, zones, interfaces, and firewall policies into a structured model.' },
      { title: 'Map zones and interfaces', body: 'A guided wizard resolves each FortiGate interface and zone to its Palo Alto zone, interface, and virtual router equivalent before any policy is translated.' },
      { title: 'Review and validate', body: 'Objects, groups, and policies appear in an editable grid. Missing references, duplicate objects, and unmapped zones are flagged with error counts per tab before you can export.' },
      { title: 'Generate PAN-OS CLI', body: 'The tool emits `set` commands in dependency order — address objects, then groups, then zones and virtual routers, then interfaces, then security policy — so nothing references an object PAN-OS has not created yet.' },
    ],
  },
  comparison: {
    heading: 'FortiGate concepts mapped to Palo Alto PAN-OS',
    rows: [
      { concept: 'Address object', source: 'edit "SRV-WEB-01" / set subnet 10.10.10.5/32', target: 'set address SRV-WEB-01 ip-netmask 10.10.10.5/32' },
      { concept: 'Address group', source: 'edit "WEB_SERVERS" / set member SRV-WEB-01', target: 'set address-group WEB_SERVERS static [ SRV-WEB-01 ]' },
      { concept: 'Service object', source: 'edit "HTTPS" / set tcp-portrange 443', target: 'set service HTTPS protocol tcp port 443' },
      { concept: 'Zone / interface', source: 'set srcintf "port12" (bound to zone DMZ)', target: 'set zone DMZ network layer3 ethernet1/2' },
      { concept: 'Security profile', source: 'set utm-status enable / set av-profile "default"', target: 'set profiles virus default (attached via Security Profile Group)' },
      { concept: 'Firewall policy', source: 'edit 10 / set srcintf port1 / set dstintf port12 / set action accept', target: 'set rulebase security rules RULE-10 from Trust to DMZ action allow' },
      { concept: 'NAT', source: 'edit 1 / set srcaddr all / set dstaddr VIP_WEB', target: 'set rulebase nat rules NAT-1 source-translation ...' },
    ],
  },
  sciFiSamples: [
    { in: 'edit "SRV-WEB-01"\n  set subnet 10.10.10.5/32\nnext', out: ['set address SRV-WEB-01 ip-netmask 10.10.10.5/32'] },
    { in: 'edit 10\n  set srcintf "port1"\n  set dstintf "port12"\n  set service "HTTPS"\n  set action accept\nnext', out: ['set rulebase security rules RULE-10 from Trust to DMZ', 'set rulebase security rules RULE-10 service HTTPS', 'set rulebase security rules RULE-10 action allow'] },
    { in: 'edit "WEB_SERVERS"\n  set member "SRV-WEB-01" "SRV-WEB-02"\nnext', out: ['set address-group WEB_SERVERS static [ SRV-WEB-01 SRV-WEB-02 ]'] },
  ],
  benefits: [
    { title: 'No hand-retyped objects', body: 'Every address, service, and group is parsed from the source file and generated as PAN-OS CLI directly, removing transcription errors entirely.' },
    { title: 'VDOM-aware parsing', body: 'Objects and policies are kept scoped to their originating VDOM through the mapping step, instead of being flattened together by accident.' },
    { title: 'Security profile visibility', body: 'UTM profile attachments are surfaced during review instead of silently disappearing during translation.' },
    { title: 'Validated before export', body: 'Duplicate objects, invalid IP ranges, and missing group members are flagged with error counts on every tab before CLI generation.' },
    { title: 'Dependency-ordered CLI', body: 'Generated commands are sequenced so address objects and groups exist before anything references them, and zones exist before interfaces bind to them.' },
    { title: 'Runs on your own configuration', body: 'The conversion happens against a file you import — nothing is sent to a third-party cloud for processing.' },
    { title: 'SD-WAN and FortiManager scope made visible', body: 'SD-WAN link-selection rules and FortiManager-layered objects are surfaced explicitly during review instead of being silently dropped or assumed identical to a flat device backup.' },
    { title: 'NAT settings reviewed in one place', body: 'Both centralized NAT and per-policy NAT settings are parsed into a single Policies view, so nothing defined in either location gets missed during review.' },
  ],
  checklist: {
    heading: 'FortiGate to Palo Alto cutover checklist',
    items: [
      { title: 'Confirm every VDOM is accounted for', body: 'Walk through each VDOM in the source FortiGate and confirm its objects, zones, and policies appear correctly scoped in the converted configuration before generating CLI.' },
      { title: 'Verify security profile equivalents', body: 'For every FortiGate policy that carried an AV, IPS, web filtering, or application control profile, confirm the mapped PAN-OS Security Profile Group provides equivalent inspection.' },
      { title: 'Double-check interface and zone mapping', body: 'Review the interface-to-zone mapping table produced during the guided wizard step against your actual cabling and zone-trust intentions, not just name similarity.' },
      { title: 'Resolve every flagged validation error', body: 'Clear every error shown in the Objects, Services, Groups, Network, and Policies tabs — a zero-error state is the signal the configuration is ready to export.' },
      { title: 'Review generated CLI order', body: 'Confirm address and service objects appear before groups, groups before zones and interfaces, and security policy after all of the above, matching PAN-OS load order.' },
      { title: 'Account for SD-WAN and FortiManager-sourced objects', body: 'If the source FortiGate is FortiManager-managed or uses SD-WAN link selection, confirm every object a policy actually depends on was captured in the export, not left at the FortiManager or global level.' },
      { title: 'Confirm NAT rule coverage', body: 'Cross-check both centralized NAT entries and any per-policy NAT settings against the generated PAN-OS NAT rulebase before cutover.' },
      { title: 'Test in a maintenance window with rollback ready', body: 'Load the generated PAN-OS configuration during a change window with the original FortiGate configuration still available, so you can roll back quickly if traffic behaves unexpectedly.' },
    ],
  },
  faq: [
    { q: 'Does this tool support FortiGate VDOMs?', a: 'Yes. VDOM-scoped objects, zones, and policies are parsed and kept associated with their originating VDOM through the mapping step, so multi-tenant configurations are not accidentally flattened into a single policy set.' },
    { q: 'What happens to FortiGate security profiles (AV, IPS, web filtering)?', a: 'Security profile attachments on each policy are parsed and surfaced during review, so you can confirm the equivalent Palo Alto Security Profile Group before the rule is exported, rather than discovering a missing inspection profile after import.' },
    { q: 'Can I convert FortiGate NAT policies?', a: 'Yes, source and destination NAT rules are parsed alongside firewall policies and translated into PAN-OS NAT rulebase entries in dependency order, after the address objects they reference already exist.' },
    { q: 'Will the interface and zone names match automatically?', a: 'Not automatically by design — FortiGate and PAN-OS naming conventions rarely line up one-to-one. A guided mapping step lets you explicitly resolve each FortiGate interface and zone to its PAN-OS equivalent before policies are translated.' },
    { q: 'Is my FortiGate configuration uploaded anywhere?', a: 'Yes, it is uploaded securely over an encrypted connection and parsed within your own isolated account on our cloud platform; your configuration is not shared with other customers or sent to a third party.' },
    { q: 'What if an address group references an object that no longer exists?', a: 'The validation pass flags missing referenced objects and empty groups directly in the Groups tab, with a link to the affected item, so it can be fixed before CLI export instead of failing on import to the Palo Alto firewall.' },
    { q: 'How long does a typical FortiGate to Palo Alto conversion take?', a: 'Parsing and CLI generation themselves take seconds to minutes depending on configuration size; the time that varies is the review step, since it scales with how many interfaces, zones, and security profiles need explicit mapping decisions.' },
    { q: 'Can FortiManager policy package exports be imported?', a: 'The parser reads device-level FortiOS configuration exports. If a policy package is managed centrally through FortiManager, export the resolved per-device configuration so that global and package-level objects a policy depends on are included in the file you import.' },
    { q: 'How are FortiGate VIP (virtual IP) objects migrated?', a: 'VIP objects are parsed alongside NAT and firewall policies and translated into PAN-OS destination NAT rules, so the mapping between the original public-facing address and its internal target is preserved rather than requiring the VIP definition to be re-derived by hand.' },
    { q: 'What happens to SD-WAN configuration during conversion?', a: 'SD-WAN rules and performance SLA definitions are surfaced during review rather than silently translated, since PAN-OS models path selection through its own separate SD-WAN constructs with no direct one-to-one FortiOS equivalent.' },
    { q: 'Does the tool support IPsec VPN configuration?', a: 'Interface and address information relevant to VPN termination is parsed where present, though tunnel-specific phase 1/phase 2 cryptographic settings should be reviewed and configured directly in PAN-OS to match your organization\'s current security requirements rather than carried forward automatically.' },
    { q: 'Can I convert a FortiGate configuration that spans multiple VDOMs in one import?', a: 'Yes, a full FortiOS export containing several VDOMs is parsed with each VDOM\'s objects and policies kept distinct, so you can review and map each one independently before generating combined or separate PAN-OS output.' },
    { q: 'Are FortiGate address group "exclude member" entries supported?', a: 'Group membership, including nested groups, is resolved to its full member list during parsing; any exclusion semantics that do not have a direct PAN-OS address-group equivalent are flagged during validation so they can be reviewed rather than silently approximated.' },
    { q: 'What FortiOS versions does the parser support?', a: 'The parser targets the CLI configuration grammar common to modern FortiOS 6.x and 7.x releases. Older or heavily customized syntax variants are still worth reviewing carefully in the Objects tab after import.' },
    { q: 'Does it convert FortiGate traffic shaping policies?', a: 'Traffic shaping is a FortiGate-specific construct without a direct PAN-OS equivalent, so shaping policies are not auto-translated; QoS should be reconfigured natively in PAN-OS according to your target platform\'s bandwidth management approach.' },
    { q: 'Can generated PAN-OS CLI be imported directly via the GUI or Panorama?', a: 'The exported file is standard `set` command syntax, which can be pasted into the PAN-OS CLI, loaded via Panorama, or applied through your existing configuration-management pipeline like any other PAN-OS configuration snippet.' },
  ],
  closing: {
    heading: 'Ready to move off FortiGate without rewriting every rule?',
    body: 'Import a FortiOS configuration and see your first converted address objects and policies in minutes.',
  },
}
