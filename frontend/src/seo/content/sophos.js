export const sophosContent = {
  key: 'sophos',
  vendorLabel: 'Sophos',
  path: '/sophos-to-palo-alto-migration',
  title: 'Sophos XG to Palo Alto Migration Tool | Convert SF-OS to PAN-OS',
  description:
    'Convert Sophos XG (SF-OS) firewall rules, address objects, and zones to Palo Alto PAN-OS CLI automatically, with validation and dependency-ordered generation.',
  heroEyebrow: 'Sophos XG &rarr; Palo Alto Networks',
  h1: 'Sophos XG to Palo Alto Migration, Without Re-typing an XML Export',
  heroSub:
    'Convert a Sophos XG (SF-OS) configuration export — hosts, services, zones, and firewall rules — into a validated, dependency-ordered Palo Alto PAN-OS configuration.',
  intro: [
    'Sophos XG Firewall (running SF-OS) manages its configuration through a structured export — commonly XML — describing hosts and IP host groups, service definitions, predefined zones (LAN, WAN, DMZ, VPN, and any custom zones), and rule-based firewall policies managed through the XG web admin. Palo Alto PAN-OS represents the same underlying intent through address objects and address groups, service objects and service groups, zones bound to interfaces, and an ordered security rulebase — conceptually close, but structured and named differently enough that hand conversion is slow and error-prone.',
    'The practical friction starts with the export format itself. Sophos XG configuration exports are structured and verbose, with each host, service, and rule represented as a distinct XML element with its own set of attributes and nested tags. Extracting a full picture of the current policy — every zone, every rule, every group membership — by reading this XML manually is tedious even for a small ruleset, and error-prone for anything the size of a real enterprise deployment.',
    'Zones are the other detail that need care. Sophos XG ships with a fixed set of default zones and lets administrators define custom ones, and firewall rules are written in terms of those zones directly. PAN-OS also organizes policy by zone, but the zone objects, the interfaces bound to them, and the virtual router assignment all have to be created explicitly and in the right order before a security rule referencing them will import cleanly. A rule that references a zone PAN-OS has not been told about yet will fail — or worse, silently misbehave — on import.',
    'This page runs a Sophos XG to Palo Alto converter that parses the XG export directly: hosts and host groups, services, zones, and firewall rules are extracted into a structured model, zones and interfaces are resolved to Palo Alto equivalents through a guided mapping step, and PAN-OS CLI is generated in the dependency order the platform requires — address and service objects and groups first, then zones, virtual routers, and interfaces, then the security rulebase.',
    'Teams moving off Sophos XG are frequently doing so as part of a broader platform consolidation, replacing several appliances with a smaller number of Palo Alto firewalls. That makes accurate translation of the underlying policy even more important, since the resulting PAN-OS configuration often needs to represent rules and zones that used to live on more than one XG device. Parsing each source configuration into the same structured model before generation makes it possible to review consolidated zones and rule sets consistently, instead of reconciling several XML exports by hand.',
    'Sophos XG Web Policies and user-based rules add a layer that a purely address-and-service view of the configuration will miss. XG lets rules match on Active Directory users or groups and apply Web Policy content filtering as part of the same rule evaluation, blending identity and web control into firewall policy in a way PAN-OS handles through User-ID and URL Filtering profiles attached to a security rule rather than a unified web-policy object. Rules built around user or group identity are parsed and surfaced explicitly during review so the equivalent User-ID mapping and URL Filtering profile can be configured deliberately, instead of the identity condition being silently dropped and the rule becoming broader than originally intended.',
    'Sophos XG\'s SD-WAN capability, layered on top of its standard routing and firewall rules, is another area worth planning for rather than assuming a direct translation. SD-WAN policy routes on XG select an outbound link based on application or performance criteria evaluated alongside the firewall rule match — a combination that does not map one-to-one to PAN-OS SD-WAN subscription constructs. As with the other vendor pairs on this site, SD-WAN configuration is surfaced as an explicit, reviewable item rather than silently approximated, so a network architect can decide how to reproduce that link-selection behavior on the target platform.',
  ],
  challenges: {
    heading: 'What makes Sophos XG to Palo Alto migration slow to do by hand',
    items: [
      {
        title: 'The configuration export is dense structured XML',
        body: 'Sophos XG exports represent every host, service, and rule as XML with nested attributes. Reading through this manually to reconstruct a full rule set — especially group memberships — is slow and easy to get wrong at any real scale.',
      },
      {
        title: 'Default and custom zones need explicit mapping',
        body: 'XG rules reference its built-in zones (LAN, WAN, DMZ, VPN) plus any custom zones directly. Each one has to be explicitly recreated as a PAN-OS zone bound to the right interface and virtual router before a translated security rule referencing it will make sense.',
      },
      {
        title: 'Host groups and rule groups add an extra layer of indirection',
        body: 'XG lets rules apply to IP host groups and organizes rules into rule groups for readability in the admin console. Neither concept maps directly to a flat PAN-OS rulebase, so preserving intent — not just literal syntax — takes care during translation.',
      },
      {
        title: 'Security features attached per-rule are easy to drop',
        body: 'XG rules can carry attached security features — IPS policies, web/application control, and traffic shaping — configured per rule rather than as a separate profile object. These are the details most likely to get missed when a migration focuses only on source, destination, and service.',
      },
      {
        title: 'SD-WAN link selection and identity-based Web Policies add hidden conditions',
        body: 'XG SD-WAN policy routes select outbound links based on application or performance criteria evaluated alongside firewall rules, and Web Policies can match on AD user or group identity. Neither condition is visible if a migration only looks at source, destination, and service objects.',
      },
      {
        title: 'FQDN and IP host objects are easy to conflate when retyped',
        body: 'XG host objects can be defined by static IP, IP range, network, or FQDN, each with different runtime behavior. Manually recreating them without preserving the exact object type risks turning a dynamic FQDN host into a stale static IP entry.',
      },
      {
        title: 'MTA and email protection rules live in a separate policy layer',
        body: 'Sophos XG\'s Mail Transfer Agent (MTA) rules operate independently of the main firewall rule set. A migration focused only on firewall rules can miss mail-flow policy entirely if it is not explicitly reviewed as its own category.',
      },
      {
        title: 'Rule group nesting complicates cutover sequencing',
        body: 'Rule groups can themselves be reordered relative to ungrouped rules in the XG console, and that relative ordering is easy to lose when rules are extracted and retyped individually rather than preserved as a structured, ordered export.',
      },
    ],
  },
  workflow: {
    heading: 'How the Sophos XG to Palo Alto conversion works',
    steps: [
      { title: 'Import the Sophos XG export', body: 'Upload an XG configuration export. The parser reads hosts, host groups, services, zones, and firewall rules into a structured model.' },
      { title: 'Map zones and interfaces', body: 'A guided wizard resolves each Sophos XG zone (default or custom) and its bound interface to a Palo Alto zone, interface, and virtual router before rules are translated.' },
      { title: 'Review and validate', body: 'Hosts, groups, services, and rules appear in an editable grid with per-tab error counts — missing referenced objects, empty groups, unmapped zones — flagged before export.' },
      { title: 'Generate PAN-OS CLI', body: 'Address and service objects and groups are generated first, then zones, virtual routers, and interfaces, then the security rulebase — in the order PAN-OS requires.' },
    ],
  },
  comparison: {
    heading: 'Sophos XG concepts mapped to Palo Alto PAN-OS',
    rows: [
      { concept: 'Host object', source: '<Host><Name>SRV-WEB-01</Name><IP>10.10.10.5</IP></Host>', target: 'set address SRV-WEB-01 ip-netmask 10.10.10.5/32' },
      { concept: 'IP host group', source: '<IPHostGroup><Name>WEB_SERVERS</Name><Member>SRV-WEB-01</Member></IPHostGroup>', target: 'set address-group WEB_SERVERS static [ SRV-WEB-01 ]' },
      { concept: 'Service', source: '<Service><Name>HTTPS</Name><Port>443</Port></Service>', target: 'set service HTTPS protocol tcp port 443' },
      { concept: 'Zone', source: '<Zone><Name>DMZ</Name></Zone>', target: 'set zone DMZ network layer3 ethernet1/2' },
      { concept: 'Firewall rule', source: '<Rule><SourceZone>LAN</SourceZone><Action>Accept</Action></Rule>', target: 'set rulebase security rules RULE-1 from Trust action allow' },
      { concept: 'Rule group', source: '<RuleGroup><Name>Web_Access</Name></RuleGroup>', target: 'ordered security rules within the PAN-OS rulebase' },
      { concept: 'Per-rule IPS/App control', source: '<Rule><IPSPolicy>default</IPSPolicy></Rule>', target: 'set rulebase security rules RULE-1 profile-setting group default' },
    ],
  },
  sciFiSamples: [
    { in: '<Host>\n  <Name>SRV-WEB-01</Name>\n  <IP>10.10.10.5</IP>\n</Host>', out: ['set address SRV-WEB-01 ip-netmask 10.10.10.5/32'] },
    { in: '<Rule>\n  <SourceZone>LAN</SourceZone>\n  <Action>Accept</Action>\n</Rule>', out: ['set rulebase security rules RULE-1 from Trust', 'set rulebase security rules RULE-1 action allow'] },
    { in: '<IPHostGroup>\n  <Name>WEB_SERVERS</Name>\n  <Member>SRV-WEB-01</Member>\n</IPHostGroup>', out: ['set address-group WEB_SERVERS static [ SRV-WEB-01 ]'] },
  ],
  benefits: [
    { title: 'No manual XML reading', body: 'The XG configuration export is parsed directly into structured objects, groups, zones, and rules, instead of being read line by line by an engineer.' },
    { title: 'Default and custom zones both handled', body: 'Built-in Sophos zones and any custom zones are resolved to Palo Alto equivalents through the same guided mapping step.' },
    { title: 'Group and rule-group intent preserved', body: 'IP host groups and rule groups are parsed and reflected in the generated PAN-OS configuration and rule ordering, not flattened without context.' },
    { title: 'Per-rule security features surfaced', body: 'IPS, application control, and other per-rule features are shown during review, so they are not silently dropped during translation.' },
    { title: 'Validated before export', body: 'Missing referenced objects, empty groups, and unmapped zones are flagged with error counts per tab before CLI is generated.' },
    { title: 'Dependency-ordered CLI', body: 'Address and service objects are generated before groups and rules reference them, and zones before interfaces bind to them.' },
    { title: 'Identity and SD-WAN conditions surfaced', body: 'User/group-based Web Policy rules and SD-WAN link-selection rules are called out explicitly during review so they can be reproduced deliberately with User-ID and PAN-OS SD-WAN constructs.' },
    { title: 'Host object type preserved exactly', body: 'Static IP, IP range, network, and FQDN host objects are each generated as their correct PAN-OS address object type, instead of being flattened into a single approximation.' },
  ],
  checklist: {
    heading: 'Sophos XG to Palo Alto cutover checklist',
    items: [
      { title: 'Confirm every zone was explicitly mapped', body: 'Verify each default and custom Sophos XG zone was resolved to the correct PAN-OS zone, interface, and virtual router — not left to an approximate name match.' },
      { title: 'Check consolidated configurations for overlap', body: 'If multiple XG appliances are being consolidated into fewer Palo Alto firewalls, confirm merged zones and rule sets do not silently duplicate or shadow one another.' },
      { title: 'Verify per-rule security feature mapping', body: 'Confirm every rule that carried an IPS policy or application/web control setting has an equivalent PAN-OS Security Profile Group attached.' },
      { title: 'Resolve every flagged validation error', body: 'Clear every error shown across the Objects, Services, Groups, Network, and Policies tabs before exporting the final CLI.' },
      { title: 'Review generated CLI order', body: 'Confirm address and service objects and groups appear before the rules referencing them, and zones and virtual routers before interfaces bind to them.' },
      { title: 'Redesign identity and SD-WAN conditions deliberately', body: 'For rules that matched on AD user/group identity or relied on SD-WAN link selection, confirm the equivalent User-ID mapping, URL Filtering profile, or PAN-OS SD-WAN configuration has been set up rather than assumed.' },
      { title: 'Review MTA and email protection policy separately', body: 'Confirm mail-flow rules configured under XG\'s MTA are accounted for on their own, since they operate independently of the main firewall rule set and are easy to miss in a firewall-only review.' },
      { title: 'Test in a maintenance window with rollback ready', body: 'Load the generated PAN-OS configuration during a change window with the original Sophos XG configuration still available, so you can roll back quickly if traffic behaves unexpectedly.' },
    ],
  },
  faq: [
    { q: 'What Sophos XG export format is supported?', a: 'The tool parses the structured configuration export produced by Sophos XG (SF-OS), including hosts, IP host groups, services, zones, and firewall rules.' },
    { q: 'Are default Sophos zones like LAN and WAN handled?', a: 'Yes, both the default XG zones (LAN, WAN, DMZ, VPN) and any custom zones are resolved to Palo Alto zone, interface, and virtual router equivalents through the guided mapping step.' },
    { q: 'What happens to per-rule IPS or application control settings?', a: 'These are parsed alongside each rule and surfaced during review, so the equivalent PAN-OS Security Profile Group can be confirmed before the rule is exported.' },
    { q: 'Can Sophos rule groups be preserved?', a: 'Rule groups used for organization in the XG admin console are parsed and reflected in the generated PAN-OS rule ordering, so the intent behind the grouping is not lost.' },
    { q: 'Is my Sophos XG configuration uploaded anywhere?', a: 'Yes, it is uploaded securely over an encrypted connection and parsed within your own isolated account on our cloud platform, and is not shared with other customers or sent to a third party.' },
    { q: 'What if a rule references a host group that was deleted?', a: 'The validation pass flags the missing referenced object directly in the Groups or Policies tab with a link to the affected rule, so it can be fixed before CLI export.' },
    { q: 'Can this help consolidate several Sophos XG appliances into fewer Palo Alto firewalls?', a: 'Each XG export is parsed into the same structured model, so zones and rules from multiple source appliances can be reviewed side by side before being merged into a single consolidated Palo Alto configuration.' },
    { q: 'Are Sophos Web Policies converted automatically?', a: 'Web Policy attachments and any user/group identity conditions on a rule are parsed and surfaced during review, so the equivalent PAN-OS User-ID mapping and URL Filtering profile can be configured deliberately rather than assumed.' },
    { q: 'Does the tool support SFOS exports specifically, or only XG?', a: 'Sophos XG Firewall runs SFOS, and the terms are used interchangeably here — the parser targets the structured configuration export produced by SFOS-based XG appliances.' },
    { q: 'What happens to SD-WAN policy routes?', a: 'SD-WAN link-selection rules are parsed and flagged for review rather than auto-translated, since PAN-OS handles path selection through its own separate SD-WAN subscription constructs with no direct one-to-one XG equivalent.' },
    { q: 'Can Sophos VPN configuration be migrated?', a: 'Interface and address information relevant to VPN termination is parsed where present, but tunnel-specific cryptographic and topology settings should be reviewed and configured directly in PAN-OS to match your current security requirements.' },
    { q: 'Does the tool convert Sophos DNAT/SNAT rules?', a: 'Yes, NAT rules are parsed alongside firewall rules and translated into PAN-OS NAT rulebase entries, generated after the address objects they reference already exist.' },
    { q: 'What XG firmware versions are supported?', a: 'The parser targets the structured XML export format common to modern SFOS-based XG releases (v18 and later). Very old export schemas are still worth a careful review pass through the Objects tab.' },
    { q: 'Can rule groups spanning multiple zones be converted cleanly?', a: 'Yes, rule groups are parsed with each member rule\'s own zone and match conditions intact, and the generated PAN-OS rule order reflects the original grouping rather than flattening rules without context.' },
    { q: 'Does the tool support Sophos IPHostGroup exports with FQDN members?', a: 'FQDN-based host entries are parsed and generated as PAN-OS FQDN address objects, distinct from IP-based hosts, so the object type is preserved rather than approximated as a static IP.' },
    { q: 'Can generated PAN-OS CLI from a Sophos XG migration be applied through Panorama?', a: 'Yes, the exported file uses standard `set` command syntax that can be pasted into the PAN-OS CLI, loaded through Panorama, or applied via your existing configuration-management pipeline.' },
  ],
  closing: {
    heading: 'Ready to move off Sophos XG without hand-parsing XML?',
    body: 'Import a Sophos XG configuration export and see your first converted objects and rules in minutes.',
  },
}
