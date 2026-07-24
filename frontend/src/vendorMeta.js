// Central place to describe every migration source vendor. Adding a new
// vendor to the dashboard only requires adding an entry here (plus backend
// support) — no other UI changes are needed.
export const VENDOR_META = [
  {
    key: 'fortigate',
    label: 'FortiGate',
    initials: 'FG',
    description: 'Migrate FortiGate FortiOS policies, objects, and NAT rules to Palo Alto PAN-OS.',
  },
  {
    key: 'cisco',
    label: 'Cisco ASA',
    initials: 'CA',
    description: 'Translate Cisco ASA access-lists, objects, and NAT into Palo Alto policies.',
  },
  {
    key: 'checkpoint',
    label: 'Check Point',
    initials: 'CP',
    description: 'Convert Check Point R80/R81 configurations into validated Palo Alto CLI output.',
  },
  {
    key: 'sophos',
    label: 'Sophos XG',
    initials: 'SX',
    description: 'Move Sophos XG firewall rules and objects to a ready-to-deploy PAN-OS config.',
  },
  {
    key: 'juniper_srx',
    label: 'Juniper SRX',
    initials: 'JN',
    description: 'Convert Juniper SRX (Junos "set"-style) security policies, NAT, and objects to PAN-OS.',
  },
]
