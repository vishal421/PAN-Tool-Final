// Column definitions for each editable object category. Field `key` must
// match the backend dataclass field name exactly (see
// backend/app/normalizer/models.py) since rows are saved back verbatim.
//
// type: 'text' | 'textarea' | 'select' | 'list' | 'multiselect' | 'combo' | 'checkbox' | 'number'
// 'list' fields (tags, members, ...) are edited as a comma-separated string.
// 'multiselect' fields (source_zone, source_address, service, zone
// interfaces, ...) are edited as a real array via a checkbox dropdown fed
// by dynamicOptionsKey, with a free-text "add custom value" escape hatch
// for values (like "any") that aren't in the known object list.
// readonly + compute: a display-only column whose value is derived from
// other fields on the same row (e.g. showing the IP of whichever
// interface a NAT rule's Translated Source points at) rather than stored
// on the row itself - compute(row, dynamicOptions) => string.

export const GRID_CONFIGS = {
  addresses: {
    title: 'Address Objects',
    newRow: () => ({ name: '', type: 'ip-netmask', value: '', description: '', tags: [] }),
    columns: [
      { key: 'name', label: 'Object Name', type: 'text', width: 180 },
      { key: 'type', label: 'Type', type: 'select', options: ['ip-netmask', 'ip-range', 'fqdn', 'ip-wildcard'], width: 120 },
      { key: 'value', label: 'Value (IP/Range/FQDN)', type: 'text', width: 220 },
      { key: 'description', label: 'Description', type: 'text', width: 220 },
      { key: 'tags', label: 'Tags', type: 'list', width: 160 },
    ],
  },
  address_groups: {
    title: 'Address Groups',
    newRow: () => ({ name: '', members: [], description: '' }),
    columns: [
      { key: 'name', label: 'Group Name', type: 'text', width: 180 },
      {
        key: 'members', label: 'Members', type: 'multiselect', width: 320,
        dynamicOptionsKey: 'address_object_names', strict: true, searchable: true,
        placeholder: 'Search address objects…',
      },
      { key: 'description', label: 'Description', type: 'text', width: 220 },
    ],
  },
  services: {
    title: 'Services',
    newRow: () => ({ name: '', protocol: 'tcp', dest_port: '', source_port: '', description: '' }),
    columns: [
      { key: 'name', label: 'Name', type: 'text', width: 180 },
      { key: 'protocol', label: 'Protocol', type: 'select', options: ['tcp', 'udp', 'sctp', 'icmp', 'icmp6'], width: 110 },
      { key: 'dest_port', label: 'Destination Port', type: 'text', width: 150 },
      { key: 'source_port', label: 'Source Port', type: 'text', width: 150 },
      { key: 'description', label: 'Description', type: 'text', width: 220 },
    ],
  },
  service_groups: {
    title: 'Service Groups',
    newRow: () => ({ name: '', members: [], description: '' }),
    columns: [
      { key: 'name', label: 'Group Name', type: 'text', width: 180 },
      {
        key: 'members', label: 'Members', type: 'multiselect', width: 320,
        dynamicOptionsKey: 'service_object_names', strict: true, searchable: true,
        placeholder: 'Search service objects…',
      },
      { key: 'description', label: 'Description', type: 'text', width: 220 },
    ],
  },
  interfaces: {
    title: 'Interfaces (Overview: Mapping, Zones, Virtual Routers, Subinterfaces)',
    newRow: () => ({ name: '', interface_type: 'layer3', zone: '', virtual_router: 'default', ip_address: '', netmask: '', description: '', enabled: true }),
    columns: [
      { key: 'name', label: 'Source Interface', type: 'text', width: 150, readonly: true },
      {
        key: 'pan_name', label: 'Palo Alto Interface', type: 'combo', width: 190,
        options: Array.from({ length: 24 }, (_, i) => `ethernet1/${i + 1}`),
        placeholder: 'ethernet1/1 or ethernet1/1.100 for a subinterface',
      },
      { key: 'interface_type', label: 'Type', type: 'select', options: ['layer3', 'layer2', 'vwire'], width: 110 },
      {
        key: 'zone', label: 'Zone', type: 'combo', width: 160,
        dynamicOptionsKey: 'zone_names', placeholder: 'Pick or type a new zone name',
      },
      { key: 'virtual_router', label: 'Virtual Router', type: 'text', width: 140 },
      { key: 'vlan', label: 'VLAN Tag (subinterface)', type: 'number', width: 150 },
      { key: 'ip_address', label: 'IP Address', type: 'text', width: 140 },
      { key: 'netmask', label: 'Netmask', type: 'text', width: 140 },
      { key: 'description', label: 'Comment', type: 'text', width: 200 },
      { key: 'enabled', label: 'Enabled', type: 'checkbox', width: 90 },
    ],
  },
  zones: {
    title: 'Zones',
    hint: 'Zones extracted from the uploaded backup appear here automatically. You can also add new ones - '
      + 'assign a zone to an interface on the Interface Mapping tab to make it take effect in the generated config.',
    newRow: () => ({ name: '', interfaces: [], description: '' }),
    columns: [
      { key: 'name', label: 'Zone Name', type: 'text', width: 160 },
      {
        key: 'interfaces', label: 'Member Interfaces', type: 'multiselect', width: 260,
        dynamicOptionsKey: 'interface_names',
      },
      { key: 'description', label: 'Description', type: 'text', width: 240 },
    ],
  },
  policies: {
    title: 'Security Policies',
    newRow: () => ({
      name: '', source_zone: ['any'], dest_zone: ['any'], source_address: ['any'], dest_address: ['any'],
      service: ['any'], application: ['any'], action: 'deny', log_start: false, log_end: true,
      description: '', disabled: false, tags: [], log_forwarding_profile: '', security_profile_group: '',
    }),
    columns: [
      { key: 'name', label: 'Rule Name', type: 'text', width: 160 },
      { key: 'source_zone', label: 'Source Zone', type: 'multiselect', width: 170, dynamicOptionsKey: 'zone_names', includeAny: true },
      { key: 'dest_zone', label: 'Dest Zone', type: 'multiselect', width: 170, dynamicOptionsKey: 'zone_names', includeAny: true },
      { key: 'source_address', label: 'Source Address', type: 'multiselect', width: 200, dynamicOptionsKey: 'address_names', includeAny: true },
      { key: 'dest_address', label: 'Dest Address', type: 'multiselect', width: 200, dynamicOptionsKey: 'address_names', includeAny: true },
      { key: 'service', label: 'Service', type: 'multiselect', width: 180, dynamicOptionsKey: 'service_names', includeAny: true },
      {
        key: 'application', label: 'Application', type: 'multiselect', width: 180,
        dynamicOptionsKey: 'application_names', includeAny: true, searchable: true,
        placeholder: 'Search applications…',
      },
      { key: 'action', label: 'Action', type: 'select', options: ['allow', 'deny', 'drop', 'reset-client'], width: 120, bulkEditable: true },
      { key: 'log_start', label: 'Log Start', type: 'checkbox', width: 90 },
      { key: 'log_end', label: 'Log End', type: 'checkbox', width: 90 },
      { key: 'disabled', label: 'Disabled', type: 'checkbox', width: 90, bulkEditable: true },
      {
        key: 'log_forwarding_profile', label: 'Log Forwarding Profile', type: 'select', width: 190,
        dynamicOptionsKey: 'log_forwarding_profiles', allowBlank: true, bulkEditable: true,
      },
      {
        key: 'security_profile_group', label: 'Security Profile Group', type: 'select', width: 190,
        dynamicOptionsKey: 'security_profile_groups', allowBlank: true, bulkEditable: true,
      },
      { key: 'description', label: 'Description', type: 'text', width: 200 },
      { key: 'tags', label: 'Tags', type: 'list', width: 140 },
    ],
  },
  routes: {
    title: 'Static Routes',
    newRow: () => ({ name: '', destination: '', next_hop: '', interface: '', metric: null, virtual_router: 'default' }),
    columns: [
      { key: 'name', label: 'Route Name', type: 'text', width: 140 },
      { key: 'destination', label: 'Destination', type: 'text', width: 160 },
      {
        key: 'interface', label: 'Interface', type: 'combo', width: 170,
        dynamicOptionsKey: 'interface_names', allowBlank: true,
        placeholder: 'e.g. ethernet1/1 (from Overview)',
      },
      { key: 'next_hop', label: 'Next Hop / Gateway IP', type: 'text', width: 170 },
      { key: 'metric', label: 'Metric', type: 'number', width: 100 },
      { key: 'virtual_router', label: 'Virtual Router', type: 'text', width: 140 },
    ],
  },
  nat_rules: {
    title: 'NAT Rules',
    newRow: () => ({
      name: '', source_zone: ['any'], dest_zone: 'any', source_address: ['any'], dest_address: ['any'],
      service: '', translated_source: '', translated_dest: '', nat_type: 'static', nat_method: 'source',
      bidirectional: false, interface_based: false, egress_interface: '', egress_interface_ip: '',
      original_port: '', translated_port: '', disabled: false,
    }),
    columns: [
      { key: 'name', label: 'NAT Rule Name', type: 'text', width: 160 },
      { key: 'source_zone', label: 'Source Zone', type: 'multiselect', width: 160, dynamicOptionsKey: 'zone_names', includeAny: true },
      { key: 'dest_zone', label: 'Dest Zone', type: 'combo', width: 150, dynamicOptionsKey: 'zone_names', allowBlank: true },
      { key: 'source_address', label: 'Source Address', type: 'multiselect', width: 180, dynamicOptionsKey: 'address_names', includeAny: true },
      { key: 'dest_address', label: 'Dest Address', type: 'multiselect', width: 180, dynamicOptionsKey: 'address_names', includeAny: true },
      { key: 'service', label: 'Service', type: 'combo', width: 150, dynamicOptionsKey: 'service_names', allowBlank: true },
      {
        key: 'nat_method', label: 'Direction', type: 'select', width: 130,
        options: ['source', 'destination', 'bidirectional'], bulkEditable: true,
      },
      {
        key: 'nat_type', label: 'NAT Type', type: 'select', width: 150,
        options: ['static', 'dynamic-ip', 'dynamic-ip-and-port'], bulkEditable: true,
      },
      // Direct egress-interface pick for interface-based source NAT (PAN-OS
      // "source-translation dynamic-ip-and-port interface-address interface
      // ethernetX/Y"). Selecting one here always resolves cleanly at
      // export, no Interface Mapping step required.
      {
        key: 'egress_interface', label: 'Egress Interface', type: 'select', width: 160,
        options: Array.from({ length: 24 }, (_, i) => `ethernet1/${i + 1}`), allowBlank: true,
        bulkEditable: true, placeholder: 'Select ethernet1/1–24',
      },
      {
        key: 'egress_interface_ip', label: 'Translated IP', type: 'text', width: 170,
        placeholder: 'Translated IP',
      },
      { key: 'translated_dest', label: 'Translated Destination', type: 'text', width: 170 },
      { key: 'original_port', label: 'Original Port', type: 'text', width: 110 },
      { key: 'translated_port', label: 'Translated Port', type: 'text', width: 110 },
      { key: 'interface_based', label: 'Force Egress IP (optional)', type: 'checkbox', width: 130 },
      { key: 'bidirectional', label: 'Bidirectional', type: 'checkbox', width: 100 },
      { key: 'disabled', label: 'Disabled', type: 'checkbox', width: 90, bulkEditable: true },
    ],
  },
  ldap_profiles: {
    title: 'LDAP Server Profiles',
    newRow: () => ({ name: '', servers: [], base_dn: '', bind_dn: '', ssl_mode: 'none', timeout: null }),
    columns: [
      { key: 'name', label: 'Profile Name', type: 'text', width: 160 },
      { key: 'servers', label: 'Servers', type: 'list', width: 220, placeholder: 'host or host:port' },
      { key: 'base_dn', label: 'Base DN', type: 'text', width: 220 },
      { key: 'bind_dn', label: 'Bind DN', type: 'text', width: 220 },
      { key: 'ssl_mode', label: 'SSL Mode', type: 'select', options: ['none', 'ldaps', 'starttls'], width: 120, bulkEditable: true },
      { key: 'timeout', label: 'Timeout (s)', type: 'number', width: 110 },
    ],
  },
  radius_profiles: {
    title: 'RADIUS Server Profiles',
    newRow: () => ({ name: '', servers: [], shared_secret: '', auth_port: 1812, acct_port: null, timeout: null, retries: null }),
    columns: [
      { key: 'name', label: 'Profile Name', type: 'text', width: 160 },
      { key: 'servers', label: 'Servers', type: 'list', width: 220, placeholder: 'host' },
      { key: 'auth_port', label: 'Auth Port', type: 'number', width: 110 },
      { key: 'acct_port', label: 'Accounting Port', type: 'number', width: 130 },
      { key: 'timeout', label: 'Timeout (s)', type: 'number', width: 110 },
      { key: 'retries', label: 'Retries', type: 'number', width: 100 },
    ],
  },
  tacacs_profiles: {
    title: 'TACACS+ Server Profiles',
    newRow: () => ({
      name: '', servers: [], timeout: null,
      use_for_authentication: true, use_for_authorization: false, use_for_accounting: false,
    }),
    columns: [
      { key: 'name', label: 'Profile Name', type: 'text', width: 160 },
      { key: 'servers', label: 'Servers', type: 'list', width: 220, placeholder: 'host or host:port' },
      { key: 'timeout', label: 'Timeout (s)', type: 'number', width: 110 },
      { key: 'use_for_authentication', label: 'Authentication', type: 'checkbox', width: 110 },
      { key: 'use_for_authorization', label: 'Authorization', type: 'checkbox', width: 110 },
      { key: 'use_for_accounting', label: 'Accounting', type: 'checkbox', width: 100 },
    ],
  },
  snmp_profiles: {
    title: 'SNMP Configuration',
    newRow: () => ({ name: '', version: 'v2c', community: '', trap_destinations: [], contact: '', location: '' }),
    columns: [
      { key: 'name', label: 'Profile Name', type: 'text', width: 150 },
      { key: 'version', label: 'Version', type: 'select', options: ['v2c', 'v3'], width: 100, bulkEditable: true },
      { key: 'community', label: 'Community String', type: 'text', width: 160 },
      { key: 'trap_destinations', label: 'Trap Destinations', type: 'list', width: 200, placeholder: 'host or host:port' },
      { key: 'contact', label: 'Contact', type: 'text', width: 150 },
      { key: 'location', label: 'Location', type: 'text', width: 150 },
    ],
  },
  syslog_profiles: {
    title: 'Syslog Server Profiles',
    newRow: () => ({
      name: '', server: '', port: 514, transport: 'UDP', facility: 'LOG_USER',
      log_format: 'BSD', source_interface: '',
    }),
    columns: [
      { key: 'name', label: 'Profile Name', type: 'text', width: 160 },
      { key: 'server', label: 'Server', type: 'text', width: 160 },
      { key: 'port', label: 'Port', type: 'number', width: 100 },
      { key: 'transport', label: 'Transport', type: 'select', options: ['UDP', 'TCP'], width: 100, bulkEditable: true },
      { key: 'facility', label: 'Facility', type: 'text', width: 130 },
      { key: 'log_format', label: 'Format', type: 'select', options: ['BSD', 'IETF'], width: 100, bulkEditable: true },
      { key: 'source_interface', label: 'Source Interface/IP', type: 'text', width: 160 },
    ],
  },
  ntp_profiles: {
    title: 'NTP Configuration',
    newRow: () => ({ name: 'ntp', primary_server: '', secondary_server: '', authentication: false, timezone: '' }),
    columns: [
      { key: 'primary_server', label: 'Primary Server', type: 'text', width: 170 },
      { key: 'secondary_server', label: 'Secondary Server', type: 'text', width: 170 },
      { key: 'authentication', label: 'Authentication', type: 'checkbox', width: 120 },
      { key: 'timezone', label: 'Timezone', type: 'text', width: 160 },
    ],
  },
  dns_profiles: {
    title: 'DNS Configuration',
    newRow: () => ({ name: 'dns', primary_dns: '', secondary_dns: '', domain_name: '', search_domain: '', dns_proxy_enabled: false }),
    columns: [
      { key: 'primary_dns', label: 'Primary DNS', type: 'text', width: 150 },
      { key: 'secondary_dns', label: 'Secondary DNS', type: 'text', width: 150 },
      { key: 'domain_name', label: 'Domain Name', type: 'text', width: 170 },
      { key: 'search_domain', label: 'Search Domain', type: 'text', width: 170 },
      { key: 'dns_proxy_enabled', label: 'DNS Proxy Used', type: 'checkbox', width: 120 },
    ],
  },
}

export const GRID_CATEGORY_ORDER = [
  'addresses', 'address_groups', 'services', 'service_groups', 'interfaces', 'zones', 'routes', 'nat_rules',
  'policies', 'ldap_profiles', 'radius_profiles', 'tacacs_profiles', 'snmp_profiles', 'syslog_profiles',
  'ntp_profiles', 'dns_profiles',
]

// Maps a ConversionIssue's object_type (backend-side, singular) to the grid
// category key (frontend-side, plural) it should be highlighted on.
export const OBJECT_TYPE_TO_CATEGORY = {
  address: 'addresses',
  address_group: 'address_groups',
  service: 'services',
  service_group: 'service_groups',
  interface: 'interfaces',
  zone: 'zones',
  route: 'routes',
  policy: 'policies',
  nat: 'nat_rules',
  ldap: 'ldap_profiles',
  radius: 'radius_profiles',
  tacacs: 'tacacs_profiles',
  snmp: 'snmp_profiles',
  syslog: 'syslog_profiles',
  ntp: 'ntp_profiles',
  dns: 'dns_profiles',
}

const LIST_FIELD_KEYS = new Set()
Object.values(GRID_CONFIGS).forEach((cfg) => {
  cfg.columns.forEach((c) => {
    if (c.type === 'list') LIST_FIELD_KEYS.add(c.key)
  })
})

// Rows come back from the API with real arrays for list fields; the grid
// edits them as comma-joined strings. These two helpers convert at the
// load/save boundary so EditableGrid itself doesn't need to know per-field.
export function rowToDisplay(row) {
  const out = { ...row }
  for (const key of Object.keys(out)) {
    if (LIST_FIELD_KEYS.has(key) && Array.isArray(out[key])) {
      out[key] = out[key].join(', ')
    }
  }
  return out
}

export function rowToPayload(row) {
  const out = { ...row }
  for (const key of Object.keys(out)) {
    if (LIST_FIELD_KEYS.has(key) && typeof out[key] === 'string') {
      out[key] = out[key].split(',').map((s) => s.trim()).filter(Boolean)
    }
  }
  return out
}
