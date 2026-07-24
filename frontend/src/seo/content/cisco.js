export const ciscoContent = {
  key: 'cisco',
  vendorLabel: 'Cisco ASA',
  path: '/cisco-to-palo-alto-migration',
  title: 'Cisco ASA to Palo Alto Migration Tool | Convert ACLs & NAT to PAN-OS',
  description:
    'Convert Cisco ASA access-lists, object-groups, and NAT rules to Palo Alto PAN-OS CLI automatically. Preserve interface security levels, objects, and rule order.',
  heroEyebrow: 'Cisco ASA &rarr; Palo Alto Networks',
  h1: 'Cisco ASA to Palo Alto Migration, Without Re-deriving Every ACL by Hand',
  heroSub:
    'Convert Cisco ASA object-groups, access-lists, twice-NAT and auto-NAT rules, and interface security levels into a validated, dependency-ordered Palo Alto PAN-OS configuration.',
  intro: [
    'Cisco ASA firewalls express policy through access-lists applied to interfaces, with permit and deny entries built from network and service object-groups, and NAT handled as its own — sometimes confusingly ordered — set of static and dynamic translation rules. Palo Alto Networks PAN-OS expresses the same intent through zone-based security rules and a separate NAT rulebase, referencing address objects, address groups, and service objects directly. The concepts overlap, but the mechanics are different enough that a manual, line-by-line rewrite is where most Cisco ASA to Palo Alto migrations lose accuracy.',
    'One of the biggest gaps is that ASA security is fundamentally interface- and security-level driven — "inside" is more trusted than "outside" by convention, and same-security-level traffic has its own special-case rules — while PAN-OS is explicitly zone-based, with every interface bound to a named zone and every security rule written in terms of source and destination zones. Translating an ASA configuration correctly means resolving each `nameif` interface to its zone equivalent before a single access-list entry can be translated into a meaningful PAN-OS security rule.',
    'NAT is the other place manual conversions tend to go wrong. ASA supports both "twice NAT" (explicit, ordered NAT statements) and auto-NAT (attached to the object definition itself), and the two can coexist in the same configuration with ASA-specific rules about which takes precedence. PAN-OS uses a single ordered NAT rulebase with its own source- and destination-translation syntax. Getting this right means parsing both ASA NAT styles into a common model and re-expressing that model in PAN-OS NAT rule order — not simply converting each NAT line independently and hoping the resulting order still makes sense.',
    'This page runs a Cisco ASA to Palo Alto converter that handles both of those problems directly: it imports an ASA configuration export, parses object-groups, access-lists, and both NAT styles into a structured model, walks you through mapping ASA interfaces and security levels to PAN-OS zones, and generates PAN-OS CLI in the dependency order the platform actually requires — address and service objects and groups first, then zones, virtual routers, and interfaces, then the security and NAT rulebases.',
    'Many ASA deployments being migrated today have been in place for a long time, which means the running-config has usually accumulated years of incremental changes: object-groups added for one project and never cleaned up, access-list entries with a zero hit count, and NAT rules layered on top of each other as the network grew. A structured parse-and-review workflow turns that accumulated complexity into something a network engineer can actually audit before cutover, rather than something that only becomes visible the first time a converted rule behaves unexpectedly in production.',
    'Cisco Firepower, managed through FMC, is a different migration surface than a standalone ASA, even though both ultimately run Cisco firewall hardware. Firepower policy is built around access control policies, intrusion policies, and file/malware policies managed centrally by FMC rather than a flat running-config, and its object model (network objects, port objects, security zones) is deliberately closer to a modern zone-based model than classic ASA. When the source is FMC-managed, exporting the effective per-device configuration — rather than assuming the FMC policy and the device behavior are identical — is worth confirming before import, since local overrides and shared policy layers can otherwise diverge from what actually gets enforced.',
    'AnyConnect remote-access VPN configuration is commonly present in an ASA export and worth planning for separately from the site-to-site and firewall policy conversion. AnyConnect ties together group-policies, connection profiles, and address pools in a way that has no line-for-line PAN-OS equivalent — Palo Alto handles remote access through GlobalProtect, with its own portal, gateway, and authentication profile constructs. Rather than attempting an unreliable automatic mapping, the parser surfaces AnyConnect-related configuration as an explicit item for review, so a network architect can deliberately redesign remote access on GlobalProtect using the ASA configuration as a reference rather than a template to copy literally.',
  ],
  challenges: {
    heading: 'Where Cisco ASA to Palo Alto conversions go wrong by hand',
    items: [
      {
        title: 'Security levels do not exist in PAN-OS',
        body: 'ASA security relies on numeric security levels per interface, with implicit rules about same-security-level and higher-to-lower traffic. PAN-OS has no equivalent concept — every permitted flow has to become an explicit zone-to-zone security rule, which is easy to under- or over-specify by hand.',
      },
      {
        title: 'Object-groups nest and get reused across ACLs',
        body: 'ASA network and service object-groups are frequently reused across many access-lists. Manually retyping them into PAN-OS address and service groups risks silently duplicating or diverging a group that was supposed to stay identical everywhere it is used.',
      },
      {
        title: 'Twice-NAT and auto-NAT can coexist',
        body: 'A single ASA configuration can mix explicit twice-NAT statements with auto-NAT rules attached to object definitions, each with ASA-specific precedence rules. Converting NAT rule-by-rule without accounting for that precedence produces a PAN-OS NAT rulebase that does not behave the same way in practice.',
      },
      {
        title: 'Access-list hit-count and remarks carry migration-relevant context',
        body: 'ASA access-list remarks and long-unused entries with zero hit counts are often the only documentation of why a rule exists. That context is easy to lose entirely during a manual retype, leaving the PAN-OS rulebase harder to audit than the original.',
      },
      {
        title: 'AnyConnect and FMC-managed policy do not map one-to-one',
        body: 'AnyConnect remote-access configuration has no direct PAN-OS equivalent — GlobalProtect uses a different portal/gateway model entirely — and FMC-managed Firepower devices can mix shared policy with local overrides. Both require deliberate redesign decisions, not a literal line-by-line conversion.',
      },
      {
        title: 'ACL entry order determines behavior, and it is easy to disturb',
        body: 'Cisco access-lists are evaluated top-down with an implicit deny at the end, and a single reordered or skipped entry during a manual retype can silently change which traffic is permitted well before anyone notices in testing.',
      },
      {
        title: 'Time-based and object-group-based ACL entries mix syntax styles',
        body: 'A single access-list can combine inline addresses, object-group references, and time-range restrictions in the same entry. Manually tracking which style applies to which line is a common source of transcription mistakes.',
      },
      {
        title: 'Interface nameif and redundant/port-channel interfaces complicate zone mapping',
        body: 'ASA nameif aliases can be bound to physical, redundant, or port-channel interfaces in ways that are not obvious from the running-config alone, making it easy to bind a PAN-OS zone to the wrong underlying interface without a guided mapping step.',
      },
    ],
  },
  workflow: {
    heading: 'How the Cisco ASA to Palo Alto conversion works',
    steps: [
      { title: 'Import the ASA configuration', body: 'Upload a Cisco ASA running-config export. The parser reads object-groups, access-lists, both NAT styles, and interface/security-level definitions into a structured model.' },
      { title: 'Map interfaces and security levels', body: 'A guided wizard resolves each ASA `nameif` interface and security level to a Palo Alto zone, interface, and virtual router before ACLs are translated into security rules.' },
      { title: 'Review and validate', body: 'Object-groups, access-lists, and NAT rules appear in an editable grid with per-tab error counts — missing referenced objects, invalid ports, empty groups — flagged before export.' },
      { title: 'Generate PAN-OS CLI', body: 'Address and service objects and groups are generated first, then zones, virtual routers, and interfaces, then the security rulebase, then NAT — matching PAN-OS dependency requirements.' },
    ],
  },
  comparison: {
    heading: 'Cisco ASA concepts mapped to Palo Alto PAN-OS',
    rows: [
      { concept: 'Network object', source: 'object network SRV-WEB-01 / host 10.10.10.5', target: 'set address SRV-WEB-01 ip-netmask 10.10.10.5/32' },
      { concept: 'Object-group', source: 'object-group network WEB_SERVERS', target: 'set address-group WEB_SERVERS static [ SRV-WEB-01 ]' },
      { concept: 'Interface & security level', source: 'nameif outside / security-level 0', target: 'set zone Untrust network layer3 ethernet1/1' },
      { concept: 'Access-list entry', source: 'access-list OUTSIDE_IN extended permit tcp any any eq 443', target: 'set rulebase security rules RULE-1 from Untrust to DMZ service HTTPS action allow' },
      { concept: 'Auto-NAT', source: 'object network SRV-WEB-01 / nat (inside,outside) static 203.0.113.10', target: 'set rulebase nat rules NAT-1 source-translation static-ip 203.0.113.10' },
      { concept: 'Twice-NAT', source: 'nat (inside,outside) source static SRV-WEB-01 SRV-WEB-01', target: 'set rulebase nat rules NAT-2 source-translation ... destination-translation ...' },
      { concept: 'Same-security-level traffic', source: 'same-security-traffic permit inter-interface', target: 'explicit zone-to-zone security rule (no implicit equivalent)' },
    ],
  },
  sciFiSamples: [
    { in: 'object network SRV-WEB-01\n  host 10.10.10.5', out: ['set address SRV-WEB-01 ip-netmask 10.10.10.5/32'] },
    { in: 'access-list OUTSIDE_IN extended permit tcp any any eq 443', out: ['set rulebase security rules RULE-1 from Untrust to DMZ', 'set rulebase security rules RULE-1 service HTTPS', 'set rulebase security rules RULE-1 action allow'] },
    { in: 'nat (inside,outside) static SRV-WEB-01 203.0.113.10', out: ['set rulebase nat rules NAT-1 source-translation static-ip 203.0.113.10'] },
  ],
  benefits: [
    { title: 'Security levels resolved explicitly', body: 'ASA interface security levels are turned into explicit PAN-OS zone assignments during mapping, instead of leaving implicit trust relationships to be reverse-engineered by hand.' },
    { title: 'Object-groups deduplicated correctly', body: 'Reused ASA object-groups are parsed once and referenced consistently across every generated PAN-OS rule, instead of risking divergent copies.' },
    { title: 'Both NAT styles handled', body: 'Twice-NAT and auto-NAT entries are parsed into a common model and re-expressed as an ordered PAN-OS NAT rulebase that preserves the original translation behavior.' },
    { title: 'Validated before export', body: 'Missing referenced objects, invalid ports, and empty object-groups are flagged with error counts per tab before CLI generation.' },
    { title: 'Dependency-ordered CLI', body: 'Address and service objects are generated before groups and rules reference them, and zones before interfaces bind to them.' },
    { title: 'Securely processed in your account', body: 'The ASA configuration you import is parsed and converted in your own isolated account on our cloud platform, never shared with other customers.' },
    { title: 'Remote-access and FMC scope surfaced', body: 'AnyConnect configuration and FMC-specific policy layers are called out explicitly during review instead of being silently approximated by an automatic translation.' },
    { title: 'ACL order and intent preserved', body: 'Access-list entries, including remarks and time-range associations, are parsed in their original order so the generated PAN-OS rulebase reflects the same evaluation intent as the source ASA policy.' },
  ],
  checklist: {
    heading: 'Cisco ASA to Palo Alto cutover checklist',
    items: [
      { title: 'Confirm zone assignment for every interface', body: 'Verify each ASA nameif interface and security level was mapped to the intended PAN-OS zone, not just an approximate name match, before generating security rules.' },
      { title: 'Check NAT precedence was preserved', body: 'Where twice-NAT and auto-NAT coexisted in the original ASA config, confirm the generated PAN-OS NAT rulebase order still produces the same effective translation behavior.' },
      { title: 'Review low-hit-count access-list entries', body: 'Decide deliberately whether long-unused ACL entries should be carried forward into the new PAN-OS rulebase or retired during the migration.' },
      { title: 'Resolve every flagged validation error', body: 'Clear every error shown across the Objects, Services, Groups, Network, and Policies tabs before exporting the final CLI.' },
      { title: 'Review generated CLI order', body: 'Confirm address and service objects and groups appear before the rules referencing them, and zones and virtual routers before interfaces bind to them.' },
      { title: 'Plan GlobalProtect separately from AnyConnect', body: 'Treat the ASA AnyConnect configuration as reference material rather than something to carry forward automatically, and design the GlobalProtect portal, gateway, and authentication profiles deliberately.' },
      { title: 'Confirm interface-to-zone bindings for redundant/port-channel interfaces', body: 'Double-check that nameif aliases bound to redundant or port-channel interfaces map to the intended physical PAN-OS interface, not just a plausible-looking name.' },
      { title: 'Test in a maintenance window with rollback ready', body: 'Load the generated PAN-OS configuration during a change window with the original ASA configuration still available, so you can roll back quickly if traffic behaves unexpectedly.' },
    ],
  },
  faq: [
    { q: 'Does this support both ASA twice-NAT and auto-NAT?', a: 'Yes, both NAT styles are parsed into a common model and generated as an ordered PAN-OS NAT rulebase, so ASA-specific precedence between the two is accounted for instead of converting each line in isolation.' },
    { q: 'How are ASA security levels handled?', a: 'Security levels are not a native PAN-OS concept, so each ASA interface and its security level are resolved to an explicit Palo Alto zone during the guided mapping step, and every implied traffic flow becomes an explicit zone-to-zone security rule.' },
    { q: 'Can object-groups reused across many access-lists be converted once?', a: 'Yes. Object-groups are parsed once into PAN-OS address or service groups and referenced consistently wherever the original ASA configuration reused them, rather than being duplicated per access-list.' },
    { q: 'What happens to access-list remarks?', a: 'Remarks are parsed alongside their associated access-list entries so the original documentation context is preserved during review, rather than being discarded during translation.' },
    { q: 'Is my ASA configuration uploaded anywhere?', a: 'Yes, it is uploaded securely over an encrypted connection and parsed within your own isolated account on our cloud platform - it is not shared with other customers or sent to a third party.' },
    { q: 'What if an access-list references an object-group that does not exist?', a: 'The validation pass flags the missing referenced object directly in the Groups or Policies tab with a link to the affected rule, so it can be corrected before CLI export.' },
    { q: 'Can this help identify unused ACL entries before migration?', a: 'The parsed rule inventory in the review grid makes zero-hit-count and otherwise dormant access-list entries visible alongside active ones, so you can make a deliberate decision about each one instead of carrying every legacy line forward by default.' },
    { q: 'Does the tool support Cisco Firepower (FMC-managed) exports?', a: 'Yes, provided the export represents the effective per-device configuration. FMC-managed policy can mix shared and local layers, so exporting the resolved device configuration rather than the raw FMC policy definition gives the most accurate parse.' },
    { q: 'Is AnyConnect configuration migrated automatically?', a: 'No. AnyConnect has no direct PAN-OS equivalent — GlobalProtect uses its own portal, gateway, and authentication model — so AnyConnect configuration is surfaced as a reference item for a deliberate GlobalProtect redesign rather than translated line by line.' },
    { q: 'How are ASA object-groups with nested object-groups handled?', a: 'Nested object-group membership is resolved recursively to its full member list during parsing and generated as a corresponding PAN-OS address or service group, so multi-level nesting does not need to be traced by hand.' },
    { q: 'Does the tool convert ASA routing configuration?', a: 'Static routes are parsed alongside interface and virtual-router context; dynamic routing protocol configuration should be reviewed and reconfigured natively in PAN-OS according to your target routing design.' },
    { q: 'What ASA software versions are supported?', a: 'The parser targets the object-group, access-list, and NAT syntax common to modern ASA 9.x running-configs. Older syntax variants are still worth a careful pass through the Objects and Policies tabs after import.' },
    { q: 'Can access-list entries with inline object definitions (not object-groups) be converted?', a: 'Yes, both object-group references and inline address/service definitions within an access-list entry are parsed and translated into the equivalent PAN-OS address or service reference.' },
    { q: 'What happens to ASA time-based access-list entries?', a: 'Time-range associations are parsed and surfaced during review, since PAN-OS schedules security rules through its own Schedule object rather than an ASA-style time-range, and the equivalent should be configured deliberately.' },
    { q: 'Does the converter flag ACL entries using deprecated protocol keywords?', a: 'Yes, access-list entries referencing protocol or service syntax with no direct PAN-OS service equivalent are flagged during validation instead of being silently dropped from the generated rule.' },
    { q: 'Can generated PAN-OS CLI for ASA migrations be loaded through Panorama?', a: 'Yes, the exported file uses standard `set` command syntax that can be pasted into the PAN-OS CLI, loaded through Panorama, or applied via your existing configuration-management pipeline.' },
  ],
  closing: {
    heading: 'Ready to stop re-deriving ACLs into PAN-OS syntax by hand?',
    body: 'Import a Cisco ASA configuration and see your first converted objects and rules in minutes.',
  },
}
