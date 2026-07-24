"""
Static reference data: ISO-3166 countries with their calling ("dial") codes
and flag emoji. Single source of truth for both signup-form validation and
the searchable country / country-code dropdowns on the frontend (served via
GET /api/meta/countries so the two never drift apart).

Flag emoji are derived from the ISO2 code (regional indicator symbols), so
no separate flag assets are needed.
"""

from __future__ import annotations


def _flag(iso2: str) -> str:
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso2.upper())


# (iso2, name, dial_code) - dial codes are the most common "+N" prefix for
# the country. A few countries share a dial code (e.g. NANP members share
# +1) - that's expected and fine for a "country code... with manual
# override allowed" field.
_RAW: list[tuple[str, str, str]] = [
    ("AF", "Afghanistan", "+93"), ("AL", "Albania", "+355"), ("DZ", "Algeria", "+213"),
    ("AD", "Andorra", "+376"), ("AO", "Angola", "+244"), ("AR", "Argentina", "+54"),
    ("AM", "Armenia", "+374"), ("AU", "Australia", "+61"), ("AT", "Austria", "+43"),
    ("AZ", "Azerbaijan", "+994"), ("BH", "Bahrain", "+973"), ("BD", "Bangladesh", "+880"),
    ("BY", "Belarus", "+375"), ("BE", "Belgium", "+32"), ("BZ", "Belize", "+501"),
    ("BJ", "Benin", "+229"), ("BT", "Bhutan", "+975"), ("BO", "Bolivia", "+591"),
    ("BA", "Bosnia and Herzegovina", "+387"), ("BW", "Botswana", "+267"), ("BR", "Brazil", "+55"),
    ("BN", "Brunei", "+673"), ("BG", "Bulgaria", "+359"), ("BF", "Burkina Faso", "+226"),
    ("BI", "Burundi", "+257"), ("KH", "Cambodia", "+855"), ("CM", "Cameroon", "+237"),
    ("CA", "Canada", "+1"), ("CV", "Cape Verde", "+238"), ("CF", "Central African Republic", "+236"),
    ("TD", "Chad", "+235"), ("CL", "Chile", "+56"), ("CN", "China", "+86"),
    ("CO", "Colombia", "+57"), ("KM", "Comoros", "+269"), ("CG", "Congo", "+242"),
    ("CD", "Congo (DRC)", "+243"), ("CR", "Costa Rica", "+506"), ("HR", "Croatia", "+385"),
    ("CU", "Cuba", "+53"), ("CY", "Cyprus", "+357"), ("CZ", "Czech Republic", "+420"),
    ("DK", "Denmark", "+45"), ("DJ", "Djibouti", "+253"), ("DO", "Dominican Republic", "+1"),
    ("EC", "Ecuador", "+593"), ("EG", "Egypt", "+20"), ("SV", "El Salvador", "+503"),
    ("EE", "Estonia", "+372"), ("ET", "Ethiopia", "+251"), ("FJ", "Fiji", "+679"),
    ("FI", "Finland", "+358"), ("FR", "France", "+33"), ("GA", "Gabon", "+241"),
    ("GM", "Gambia", "+220"), ("GE", "Georgia", "+995"), ("DE", "Germany", "+49"),
    ("GH", "Ghana", "+233"), ("GR", "Greece", "+30"), ("GT", "Guatemala", "+502"),
    ("GN", "Guinea", "+224"), ("GY", "Guyana", "+592"), ("HT", "Haiti", "+509"),
    ("HN", "Honduras", "+504"), ("HK", "Hong Kong", "+852"), ("HU", "Hungary", "+36"),
    ("IS", "Iceland", "+354"), ("IN", "India", "+91"), ("ID", "Indonesia", "+62"),
    ("IR", "Iran", "+98"), ("IQ", "Iraq", "+964"), ("IE", "Ireland", "+353"),
    ("IL", "Israel", "+972"), ("IT", "Italy", "+39"), ("CI", "Ivory Coast", "+225"),
    ("JM", "Jamaica", "+1"), ("JP", "Japan", "+81"), ("JO", "Jordan", "+962"),
    ("KZ", "Kazakhstan", "+7"), ("KE", "Kenya", "+254"), ("KW", "Kuwait", "+965"),
    ("KG", "Kyrgyzstan", "+996"), ("LA", "Laos", "+856"), ("LV", "Latvia", "+371"),
    ("LB", "Lebanon", "+961"), ("LS", "Lesotho", "+266"), ("LR", "Liberia", "+231"),
    ("LY", "Libya", "+218"), ("LI", "Liechtenstein", "+423"), ("LT", "Lithuania", "+370"),
    ("LU", "Luxembourg", "+352"), ("MO", "Macau", "+853"), ("MK", "Macedonia", "+389"),
    ("MG", "Madagascar", "+261"), ("MW", "Malawi", "+265"), ("MY", "Malaysia", "+60"),
    ("MV", "Maldives", "+960"), ("ML", "Mali", "+223"), ("MT", "Malta", "+356"),
    ("MR", "Mauritania", "+222"), ("MU", "Mauritius", "+230"), ("MX", "Mexico", "+52"),
    ("MD", "Moldova", "+373"), ("MC", "Monaco", "+377"), ("MN", "Mongolia", "+976"),
    ("ME", "Montenegro", "+382"), ("MA", "Morocco", "+212"), ("MZ", "Mozambique", "+258"),
    ("MM", "Myanmar", "+95"), ("NA", "Namibia", "+264"), ("NP", "Nepal", "+977"),
    ("NL", "Netherlands", "+31"), ("NZ", "New Zealand", "+64"), ("NI", "Nicaragua", "+505"),
    ("NE", "Niger", "+227"), ("NG", "Nigeria", "+234"), ("NO", "Norway", "+47"),
    ("OM", "Oman", "+968"), ("PK", "Pakistan", "+92"), ("PA", "Panama", "+507"),
    ("PG", "Papua New Guinea", "+675"), ("PY", "Paraguay", "+595"), ("PE", "Peru", "+51"),
    ("PH", "Philippines", "+63"), ("PL", "Poland", "+48"), ("PT", "Portugal", "+351"),
    ("PR", "Puerto Rico", "+1"), ("QA", "Qatar", "+974"), ("RO", "Romania", "+40"),
    ("RU", "Russia", "+7"), ("RW", "Rwanda", "+250"), ("SA", "Saudi Arabia", "+966"),
    ("SN", "Senegal", "+221"), ("RS", "Serbia", "+381"), ("SC", "Seychelles", "+248"),
    ("SL", "Sierra Leone", "+232"), ("SG", "Singapore", "+65"), ("SK", "Slovakia", "+421"),
    ("SI", "Slovenia", "+386"), ("SO", "Somalia", "+252"), ("ZA", "South Africa", "+27"),
    ("KR", "South Korea", "+82"), ("SS", "South Sudan", "+211"), ("ES", "Spain", "+34"),
    ("LK", "Sri Lanka", "+94"), ("SD", "Sudan", "+249"), ("SR", "Suriname", "+597"),
    ("SZ", "Eswatini", "+268"), ("SE", "Sweden", "+46"), ("CH", "Switzerland", "+41"),
    ("SY", "Syria", "+963"), ("TW", "Taiwan", "+886"), ("TJ", "Tajikistan", "+992"),
    ("TZ", "Tanzania", "+255"), ("TH", "Thailand", "+66"), ("TG", "Togo", "+228"),
    ("TT", "Trinidad and Tobago", "+1"), ("TN", "Tunisia", "+216"), ("TR", "Turkey", "+90"),
    ("TM", "Turkmenistan", "+993"), ("UG", "Uganda", "+256"), ("UA", "Ukraine", "+380"),
    ("AE", "United Arab Emirates", "+971"), ("GB", "United Kingdom", "+44"),
    ("US", "United States", "+1"), ("UY", "Uruguay", "+598"), ("UZ", "Uzbekistan", "+998"),
    ("VE", "Venezuela", "+58"), ("VN", "Vietnam", "+84"), ("YE", "Yemen", "+967"),
    ("ZM", "Zambia", "+260"), ("ZW", "Zimbabwe", "+263"),
]

COUNTRIES: list[dict[str, str]] = [
    {"iso2": iso2, "name": name, "dial_code": dial, "flag": _flag(iso2)}
    for iso2, name, dial in sorted(_RAW, key=lambda row: row[1])
]

COUNTRY_BY_ISO2: dict[str, dict[str, str]] = {c["iso2"]: c for c in COUNTRIES}
VALID_ISO2_CODES: set[str] = set(COUNTRY_BY_ISO2)
VALID_DIAL_CODES: set[str] = {c["dial_code"] for c in COUNTRIES}
