export const checkpointContent = {
  key: 'checkpoint',
  vendorLabel: 'Check Point',
  path: '/checkpoint-to-palo-alto-migration',
  title: 'Check Point to Palo Alto Migration Tool | Convert R80/R81 to PAN-OS',
  description:
    'Convert Check Point R80/R81 security policies, objects, and NAT rules to Palo Alto PAN-OS CLI automatically, with dependency-ordered generation and validation.',
  heroEyebrow: 'Check Point &rarr; Palo Alto Networks',
  h1: 'Check Point to Palo Alto Migration, Minus the Manual Object Rebuild',
  heroSub:
    'Convert a Check Point R80/R81 security policy — host objects, network objects, service objects, and the unified Access and NAT layers — into validated Palo Alto PAN-OS CLI, generated in the correct dependency order.',
  intro: [
    'Check Point and Palo Alto Networks organize a security policy around fundamentally different architectures. Check Point separates the Security Management Server, which holds the object database and policy, from the Security Gateway that enforces it, and expresses that policy through a unified Access Control layer plus a separate NAT layer, typically managed through SmartConsole or the Management API. Palo Alto Networks collapses management and enforcement into the same device model (or a dedicated Panorama layer) and expresses policy as an ordered rulebase of security rules and NAT rules referencing address objects, address groups, service objects, and zones directly.',
    'That architectural gap is exactly where manual Check Point to Palo Alto migrations lose time. Object names in a Check Point database are frequently reused across contexts, and the group nesting can run several layers deep — a network group referencing another group referencing a handful of host objects. Rebuilding that hierarchy by hand in PAN-OS means recreating every object from scratch and hoping none of the nested references get dropped or duplicated along the way.',
    'Security policy translation carries its own set of details worth getting right. Check Point rules can apply to multiple gateways, reference dynamic objects, and carry track/logging settings, action types (Accept, Drop, Reject), and inline layers that do not map one-to-one to a flat PAN-OS security rule. A firewall configuration converter built for this vendor pair needs to parse the Check Point rule base into a structured model — sources, destinations, services, action, and logging intent — and then generate the closest correct PAN-OS equivalent, flagging anything that cannot be translated automatically instead of guessing.',
    'This page runs a purpose-built Check Point to Palo Alto converter: import an exported Check Point configuration, review parsed host objects, network objects, groups, services, and rules in an editable grid, resolve interface and zone mappings, and generate PAN-OS CLI in dependency order — address objects and groups before the security rules that reference them, and zones and virtual routers before the interfaces bound to them.',
    'The size of a typical Check Point estate is what makes automation worth it. A management database that has grown over several years of SmartConsole changes commonly accumulates object sprawl — near-duplicate host objects, groups nobody remembers the purpose of, and rules with logging settings that were changed once and never revisited. A firewall migration tool that parses this structure explicitly gives a security team a complete, structured inventory of what actually exists before conversion, which is often the first time that inventory has been fully visible in one place.',
    'Global Properties and Anti-Spoofing settings deserve deliberate attention during a Check Point migration because neither is expressed as an object inside the rule base itself. Global Properties configure behavior that applies across the entire policy — implied rules for core connectivity, default logging behavior, and similar settings — while Anti-Spoofing is configured per interface topology rather than as a rule. Because neither shows up as a line in the rule base export, a conversion process that only reads rules and objects will miss them entirely; they need to be reviewed and reproduced as their PAN-OS equivalents (zone protection profiles and explicit security rules) separately, as a deliberate step rather than an assumed one.',
    'Ordered and inline layers add a further layer of nuance to translating the Access Control policy correctly. R80 and later versions let administrators nest an inline layer inside a rule of a parent ordered layer, effectively creating a sub-policy that only evaluates for traffic matching the parent rule. PAN-OS has no native nested-layer construct — a security rulebase is a single ordered list — so an inline layer has to be flattened into equivalent top-level rules that preserve the same match conditions and precedence the nesting implied, which is exactly the kind of structural translation that is easy to get subtly wrong when done by hand, one rule at a time.',
  ],
  challenges: {
    heading: 'What makes Check Point migrations time-consuming to do manually',
    items: [
      {
        title: 'Management-and-gateway split has no direct PAN-OS equivalent',
        body: 'Check Point separates the policy database (Management Server) from enforcement (Security Gateway). PAN-OS keeps these closer together per firewall, or centralizes them in Panorama. Manually reconciling which gateway a given rule actually applied to is easy to get wrong.',
      },
      {
        title: 'Deeply nested object groups',
        body: 'Check Point network groups routinely nest three or four levels deep. Rebuilding that hierarchy in PAN-OS address groups by hand means tracing every nested reference manually, and it is easy to flatten or duplicate members along the way.',
      },
      {
        title: 'Access and NAT layers translate differently than a single rulebase',
        body: 'Check Point\'s unified policy separates Access Control and NAT into distinct layers that can each contain ordered sub-policies. PAN-OS expresses these as two separate rulebases (security and NAT) with their own ordering — a manual conversion has to preserve rule precedence in both places independently.',
      },
      {
        title: 'Track and logging settings are easy to lose',
        body: 'Check Point rules commonly carry a Track setting (Log, Detailed Log, Account) attached per rule. When engineers focus on getting source, destination, and service objects correct, log-forwarding intent is the detail most often left out of the PAN-OS rule.',
      },
      {
        title: 'Inline layers and Global Properties are invisible in the rule list',
        body: 'An inline layer nested inside a parent rule acts as its own sub-policy with no direct PAN-OS equivalent, and Global Properties / Anti-Spoofing settings apply outside the rule base entirely. Both are easy to overlook completely if a migration only reads the visible rule list.',
      },
      {
        title: 'Negated ("Not") match conditions are easy to invert by accident',
        body: 'Check Point rules can match "not this object" on source, destination, or service. When re-derived by hand into a PAN-OS rule, a negation that gets dropped or misapplied silently changes which traffic the rule actually covers.',
      },
      {
        title: 'Object naming collisions across the management database',
        body: 'A Check Point database accumulated over years commonly has multiple objects with similar or identical names created by different administrators. Manually retyping references risks pointing a rule at the wrong same-named object entirely.',
      },
      {
        title: 'Rule base sections and disabled rules carry meaning that is easy to lose',
        body: 'Section titles and explicitly disabled rules in SmartConsole often document intent (a rule kept for reference, a section grouping related policy). That context rarely survives a manual, line-by-line retype into a flat PAN-OS rulebase.',
      },
    ],
  },
  workflow: {
    heading: 'How the Check Point to Palo Alto conversion works',
    steps: [
      { title: 'Import the Check Point export', body: 'Upload an exported Check Point configuration. The parser reads host objects, network objects, groups, service objects, and the Access and NAT rule layers into a structured model.' },
      { title: 'Map interfaces and zones', body: 'A guided wizard resolves Check Point gateway interfaces and topology (internal/external) to Palo Alto zones, interfaces, and virtual routers before rules are translated.' },
      { title: 'Review and validate', body: 'Objects, groups, and rules appear in an editable grid with per-tab error counts — missing referenced objects, empty groups, duplicate services — so you fix issues before generating CLI.' },
      { title: 'Generate PAN-OS CLI', body: 'Commands are emitted in dependency order: address objects and groups, service objects and groups, zones and virtual routers, interfaces, then the security and NAT rulebases.' },
    ],
  },
  comparison: {
    heading: 'Check Point concepts mapped to Palo Alto PAN-OS',
    rows: [
      { concept: 'Host object', source: 'host SRV-WEB-01, ip-address 10.10.10.5', target: 'set address SRV-WEB-01 ip-netmask 10.10.10.5/32' },
      { concept: 'Network group', source: 'group-with-exclusion / simple-group WEB_SERVERS', target: 'set address-group WEB_SERVERS static [ SRV-WEB-01 ]' },
      { concept: 'Service object', source: 'service-tcp HTTPS, port 443', target: 'set service HTTPS protocol tcp port 443' },
      { concept: 'Interface topology', source: 'interface eth0, topology internal', target: 'set zone Trust network layer3 ethernet1/1' },
      { concept: 'Access rule', source: 'action Accept, track Log', target: 'set rulebase security rules RULE-1 action allow / set log-end yes' },
      { concept: 'NAT layer entry', source: 'Original: SRV-WEB-01 / Translated: VIP_WEB', target: 'set rulebase nat rules NAT-1 source-translation static-ip 203.0.113.10' },
      { concept: 'Rule base ordering', source: 'Ordered layer (Access Control policy)', target: 'set rulebase security rules RULE-1 ... (positional rule order)' },
    ],
  },
  sciFiSamples: [
    { in: 'host SRV-WEB-01\n  ip-address 10.10.10.5', out: ['set address SRV-WEB-01 ip-netmask 10.10.10.5/32'] },
    { in: 'rule: action Accept\n  source AD_10.16.9.13\n  service HTTPS\n  track Log', out: ['set rulebase security rules RULE-1 source AD_10.16.9.13', 'set rulebase security rules RULE-1 service HTTPS', 'set rulebase security rules RULE-1 action allow', 'set rulebase security rules RULE-1 log-end yes'] },
    { in: 'group WEB_SERVERS\n  members SRV-WEB-01, SRV-WEB-02', out: ['set address-group WEB_SERVERS static [ SRV-WEB-01 SRV-WEB-02 ]'] },
  ],
  benefits: [
    { title: 'Nested groups resolved automatically', body: 'Multi-level Check Point network groups are parsed and rebuilt as PAN-OS address groups without manual tracing of every nested reference.' },
    { title: 'Access and NAT layers kept separate', body: 'Security policy and NAT translations are generated as their own PAN-OS rulebases, preserving the ordering intent of each Check Point layer.' },
    { title: 'Logging intent preserved', body: 'Track settings on Check Point rules are surfaced during review so log-forwarding behavior is not silently dropped in the PAN-OS rule.' },
    { title: 'Validated object references', body: 'Missing referenced objects and empty groups are flagged with error counts per tab before CLI is generated, not discovered after policy install.' },
    { title: 'Dependency-ordered CLI output', body: 'Address and service objects are generated before the groups and rules that reference them, and zones before interfaces bind to them.' },
    { title: 'Securely processed in your account', body: 'Your Check Point export is parsed and converted in your own isolated account on our cloud platform, never shared with other customers.' },
    { title: 'Inline layers flattened deliberately', body: 'Nested inline layers are surfaced during review so their sub-policy match conditions can be reproduced as explicit, correctly ordered PAN-OS rules instead of being silently collapsed.' },
    { title: 'Negation and section context preserved', body: 'Negated match conditions and rule-base section groupings are carried into the review grid intact, instead of being lost when a rule is retyped by hand.' },
  ],
  checklist: {
    heading: 'Check Point to Palo Alto cutover checklist',
    items: [
      { title: 'Reconcile object sprawl before converting', body: 'Use the review step to spot near-duplicate host and network objects accumulated over years of SmartConsole changes, and decide which to keep before generating final CLI.' },
      { title: 'Confirm Access and NAT layer ordering separately', body: 'Check that the generated PAN-OS security rulebase and NAT rulebase each preserve the rule precedence of their originating Check Point layer.' },
      { title: 'Verify Track/logging settings per rule', body: 'Confirm every rule that had Log or Detailed Log in Check Point has equivalent log-forwarding behavior configured on its PAN-OS counterpart.' },
      { title: 'Resolve every flagged validation error', body: 'Clear every error shown across the Objects, Services, Groups, Network, and Policies tabs before exporting the final CLI.' },
      { title: 'Review generated CLI order', body: 'Confirm address and service objects and groups appear before the rules referencing them, and zones and virtual routers before interfaces bind to them.' },
      { title: 'Reproduce Global Properties and Anti-Spoofing separately', body: 'Since neither is expressed as a rule-base line item, confirm implied connectivity behavior and per-interface Anti-Spoofing settings have been deliberately reproduced as PAN-OS zone protection and security rules.' },
      { title: 'Re-verify negated rule conditions', body: 'For every rule that used a "Not" condition on source, destination, or service, confirm the equivalent PAN-OS rule negates the same match — not the opposite.' },
      { title: 'Test in a maintenance window with rollback ready', body: 'Load the generated PAN-OS configuration during a change window with the original Check Point policy still installed, so you can roll back quickly if traffic behaves unexpectedly.' },
    ],
  },
  faq: [
    { q: 'Does this handle Check Point R80 and R81 exports?', a: 'Yes, the parser is built against the object and rule-base structure common to R80 and R81 management databases, including host objects, network groups, service objects, and the Access Control and NAT layers.' },
    { q: 'What happens to Check Point Track (logging) settings?', a: 'Track settings such as Log or Detailed Log attached to each rule are parsed and shown during review, so you can confirm the equivalent PAN-OS logging configuration before the rule is exported.' },
    { q: 'Can nested Check Point network groups be converted?', a: 'Yes. Groups referencing other groups are resolved to their full member list and generated as PAN-OS address groups, so you do not have to manually trace multi-level nesting.' },
    { q: 'Are NAT rules converted along with security rules?', a: 'Yes, the NAT layer is parsed separately from the Access Control layer and generated as its own PAN-OS NAT rulebase, after the address objects it references have already been created.' },
    { q: 'Is my Check Point configuration uploaded to a cloud service?', a: 'Yes, it is uploaded securely over an encrypted connection and parsed within your own isolated account on our cloud platform; it is not shared with other customers or sent to a third party.' },
    { q: 'What if a rule references an object that was renamed or deleted?', a: 'The validation pass flags missing referenced objects directly in the Groups and Policies tabs with a link to the affected rule, so it can be corrected before CLI export.' },
    { q: 'Does the tool help clean up unused or duplicate objects?', a: 'The review grid surfaces the full parsed object inventory, including duplicates flagged by validation, giving you the visibility to decide what to consolidate before it becomes part of your Palo Alto configuration.' },
    { q: 'Are Inline Layers supported?', a: 'Inline layers nested inside a parent rule are parsed and surfaced during review, since PAN-OS has no native nested-layer construct. You confirm how each inline layer\'s conditions should be flattened into ordered top-level PAN-OS rules before export.' },
    { q: 'How are Global Properties converted?', a: 'Global Properties are not part of the rule base export, so they are not auto-translated. They are called out separately in the checklist so implied connectivity and default behavior can be deliberately reproduced through explicit PAN-OS rules and settings.' },
    { q: 'Does the tool convert Anti-Spoofing settings?', a: 'Anti-Spoofing is configured per interface topology in Check Point rather than as a rule, so it is not parsed automatically. It is flagged as a manual review item so equivalent PAN-OS zone protection can be configured deliberately.' },
    { q: 'Can VPN Communities be converted?', a: 'Interface and address information relevant to VPN endpoints is parsed where present in the export, but Community-level VPN topology and encryption domain configuration should be reviewed and reproduced directly in PAN-OS to match your current security requirements.' },
    { q: 'Does this support both R80 and R81.x Management API exports?', a: 'Yes, the parser targets the object and rule-base JSON/CLI structures common across the R80.x and R81.x Management API and SmartConsole export formats.' },
    { q: 'What happens to dynamic objects referenced in a rule?', a: 'Dynamic objects are parsed and shown in the review grid as-is; since their membership is resolved at runtime by the Security Gateway rather than statically, they are flagged so you can confirm the equivalent PAN-OS Dynamic Address Group configuration separately.' },
    { q: 'Can rules scoped to specific gateways be filtered during import?', a: 'Rules are parsed with their applies-to (installed-on) scope preserved, so during review you can identify which rules were intended for a specific gateway rather than the full estate before deciding what to carry into the target Palo Alto configuration.' },
    { q: 'How are Check Point service groups with protocol-mismatched members handled?', a: 'Service group membership is validated during the review pass, and any group mixing incompatible protocol types is flagged so it can be corrected before it is generated as a PAN-OS service group.' },
    { q: 'Can generated PAN-OS CLI for a Check Point migration be pushed through Panorama?', a: 'Yes, the exported file uses standard `set` command syntax that can be pasted into the PAN-OS CLI, loaded through Panorama, or applied via your existing configuration-management pipeline.' },
  ],
  closing: {
    heading: 'Ready to retire SmartConsole rule-by-rule rebuilding?',
    body: 'Import a Check Point configuration export and see your first converted objects and rules in minutes.',
  },
}
