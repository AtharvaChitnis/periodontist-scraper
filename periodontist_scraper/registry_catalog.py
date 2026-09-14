"""Public professional registries used as HTML scrape sources."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

COLUMNS = [
    "id",
    "country",
    "registry",
    "profession",
    "webpage",
    "record_type",
    "extraction_method",
    "skip_auto",
]

# id, country, registry, profession, webpage, record_type, extraction_method, skip_auto
_ROWS = [
    ("npi", "USA", "NPPES NPI Registry", "Doctors;Dentists;Nurses;Therapists;Other Healthcare Providers", "https://npiregistry.cms.hhs.gov/search", "Provider Registry", "HTML/API", False),
    ("nppes_bulk", "USA", "NPPES Data Dissemination", "Doctors;Dentists;Nurses;Therapists;Other Healthcare Providers", "https://download.cms.gov/nppes/", "Provider Dataset", "Bulk Download", False),
    ("cms_directory", "USA", "CMS National Provider Directory", "Healthcare Providers", "https://directory.cms.gov/", "Provider Directory", "HTML/API", False),
    ("medicare_care_compare", "USA", "Medicare Care Compare", "Healthcare Providers", "https://www.medicare.gov/care-compare/", "Healthcare Provider Directory", "HTML/API", False),
    ("dea_verification", "USA", "DEA Registration Verification", "Prescribers", "https://apps.deadiversion.usdoj.gov/", "Provider Verification", "Search", False),
    ("ca_medical_board", "USA", "California Medical Board", "Physicians", "https://www.mbc.ca.gov/License-Verification/", "Medical License Registry", "Search", False),
    ("ny_physician_lookup", "USA", "New York State Physician Lookup", "Physicians", "https://www.health.ny.gov/professionals/doctors/", "Medical Registry", "Search", False),
    ("tx_medical_board", "USA", "Texas Medical Board", "Physicians", "https://www.tmb.state.tx.us/", "Medical License Registry", "Search", False),
    ("uk_gmc", "UK", "GMC Medical Register", "Doctors;Physician Associates;Anaesthesia Associates", "https://www.gmc-uk.org/registration-and-licensing/the-medical-register", "Medical Register", "Search", False),
    ("uk_gmc_data", "UK", "GMC Data Explorer", "Doctors", "https://gde.gmc-uk.org/", "Professional Dataset", "Data Explorer", False),
    ("uk_gdc", "UK", "GDC Register", "Dentists;Dental Professionals", "https://www.gdc-uk.org/registration", "Professional Register", "Search", False),
    ("uk_gdc_specialist", "UK", "GDC Specialist Lists", "Dental Specialists", "https://www.gdc-uk.org/registration/the-register/specialist-lists", "Specialist Register", "Search", False),
    ("uk_nmc", "UK", "NMC Register", "Nurses;Midwives;Nursing Associates", "https://www.nmc.org.uk/registration/search-the-register/", "Professional Register", "Search", False),
    ("uk_hcpc", "UK", "HCPC Register", "Physiotherapists;Psychologists;Paramedics;Radiographers;Dietitians;Allied Health", "https://www.hcpc-uk.org/check-the-register/", "Professional Register", "Search", False),
    ("uk_gphc", "UK", "GPhC Register", "Pharmacists;Pharmacy Technicians", "https://www.pharmacyregulation.org/register-pharmacy-professionals", "Professional Register", "Search", False),
    ("uk_goc", "UK", "GOC Register", "Optometrists;Dispensing Opticians", "https://optical.org/en/registration/", "Professional Register", "Search", False),
    ("uk_gosc", "UK", "GOsC Register", "Osteopaths", "https://www.osteopathy.org.uk/register/", "Professional Register", "Search", False),
    ("uk_swe", "UK", "Social Work England Register", "Social Workers", "https://www.socialworkengland.org.uk/registration/search-the-register/", "Professional Register", "Search", False),
    ("au_ahpra", "Australia", "Ahpra National Register", "Doctors;Dentists;Nurses;Midwives;Pharmacists;Physiotherapists;Psychologists;Allied Health", "https://www.ahpra.gov.au/Registration/Registers-of-Practitioners.aspx", "National Professional Register", "Search/Bulk Data", False),
    ("au_medical_board", "Australia", "Medical Board of Australia", "Doctors", "https://www.medicalboard.gov.au/Registration/Registers-of-Practitioners.aspx", "Medical Register", "Search/Bulk Data", False),
    ("au_dental_board", "Australia", "Dental Board of Australia", "Dentists;Dental Specialists", "https://www.dentalboard.gov.au/Registration/Registers-of-Practitioners.aspx", "Dental Register", "Search/Bulk Data", False),
    ("au_nmba", "Australia", "Nursing and Midwifery Board", "Nurses;Midwives", "https://www.nursingmidwiferyboard.gov.au/Registration/Registers-of-Practitioners.aspx", "Nursing Register", "Search/Bulk Data", False),
    ("au_pharmacy_board", "Australia", "Pharmacy Board of Australia", "Pharmacists", "https://www.pharmacyboard.gov.au/Registration/Registers-of-Practitioners.aspx", "Pharmacy Register", "Search/Bulk Data", False),
    ("ca_cpso", "Canada", "CPSO Doctor Search", "Physicians", "https://doctors.cpso.on.ca/", "Medical Registry", "Search", False),
    ("ca_cpsa", "Canada", "CPSA Physician Directory", "Physicians", "https://search.cpsa.ca/", "Medical Registry", "Search", False),
    ("ca_cpsbc", "Canada", "CPSBC Physician Directory", "Physicians", "https://www.cpsbc.ca/public/registrant-directory", "Medical Registry", "Search", False),
    ("ca_cmq", "Canada", "College of Physicians Quebec", "Physicians", "https://www.cmq.org/", "Medical Registry", "Search", False),
    ("ca_royal_college", "Canada", "Royal College Specialist Directory", "Medical Specialists", "https://www.royalcollege.ca/", "Specialist Directory", "Search", False),
    ("nz_medical", "New Zealand", "Medical Council Register", "Doctors", "https://www.mcnz.org.nz/registration/medical-register/", "Medical Register", "Search", False),
    ("nz_dental", "New Zealand", "Dental Council Register", "Dentists", "https://www.dcnz.org.nz/resources-and-information/registration/", "Dental Register", "Search", False),
    ("nz_nursing", "New Zealand", "Nursing Council Register", "Nurses", "https://www.nursingcouncil.org.nz/Public/Find-a-nurse", "Professional Register", "Search", False),
    ("in_imr", "India", "Indian Medical Register", "Doctors", "https://www.nmc.org.in/information-desk/indian-medical-register/", "Medical Register", "Search", False),
    ("in_nmr", "India", "National Medical Register", "Doctors", "https://nmr.abdm.gov.in/", "Medical Register", "Search", False),
    ("in_hpr", "India", "Healthcare Professionals Registry", "Doctors;Dentists;Nurses;Paramedics;Allied Health", "https://hpr.abdm.gov.in/", "Healthcare Professional Registry", "Search", False),
    ("in_ndc", "India", "National Dental Commission", "Dentists;Dental Specialists", "https://dciindia.gov.in/", "Dental Register", "Search", False),
    ("in_mmc", "India", "Maharashtra Medical Council", "Doctors", "https://www.maharashtramedicalcouncil.gov.in/", "State Medical Register", "Search", False),
    ("in_mh_doctor_availability", "India", "Maharashtra Doctor Availability Registry", "Doctors", "https://healthdoctoravailability.maharashtra.gov.in/", "Government Doctor Directory", "Search", False),
    ("in_clinical_establishments", "India", "Clinical Establishments National Register", "Clinics;Hospitals;Dental Clinics;Diagnostics;Allied Health", "https://clinicalestablishments.mohfw.gov.in/", "Clinical Establishment Directory", "Web/Download", False),
    ("in_nursing", "India", "Indian Nursing Council", "Nurses;Midwives", "https://www.indiannursingcouncil.org/", "Nursing Registry", "Search", False),
    ("in_pci", "India", "Pharmacy Council of India", "Pharmacists", "https://www.pci.nic.in/", "Pharmacy Registry", "Search", False),
    ("sg_smc", "Singapore", "Medical Council Register", "Doctors", "https://prs.moh.gov.sg/prs/internet/profSearch/main.action", "Medical Register", "Search", False),
    ("sg_sdc", "Singapore", "Dental Council Register", "Dentists", "https://prs.moh.gov.sg/prs/internet/profSearch/main.action", "Dental Register", "Search", False),
    ("sg_snb", "Singapore", "Nursing Board", "Nurses;Midwives", "https://www.healthprofessionals.gov.sg/snb", "Professional Register", "Search", False),
    ("ie_medical", "Ireland", "Medical Council Register", "Doctors", "https://www.medicalcouncil.ie/public-information/check-the-register/", "Medical Register", "Search", False),
    ("ie_dental", "Ireland", "Dental Council Register", "Dentists", "https://www.dentalcouncil.ie/public-information/registered-dentists/", "Dental Register", "Search", False),
    ("za_hpcsa", "South Africa", "HPCSA Register", "Doctors;Dentists;Psychologists;Allied Health", "https://hpcsa.co.za/", "Professional Register", "Search", False),
    ("sa_scfhs", "Saudi Arabia", "SCFHS Professional Registry", "Doctors;Dentists;Nurses;Pharmacists;Allied Health", "https://www.scfhs.org.sa/", "Professional Registry", "Search", False),
    ("ae_dha", "UAE", "DHA Professional Registry", "Doctors;Dentists;Nurses;Pharmacists;Allied Health", "https://services.dha.gov.ae/", "Professional Registry", "Search", False),
    ("ae_doh", "UAE", "Department of Health Abu Dhabi", "Doctors;Dentists;Nurses;Allied Health", "https://www.doh.gov.ae/", "Professional Registry", "Search", False),
    ("nl_big", "Netherlands", "BIG Register", "Doctors;Dentists;Nurses;Pharmacists;Physiotherapists;Other Professionals", "https://www.bigregister.nl/", "Healthcare Professional Register", "Search", False),
    ("fr_rpps", "France", "Annuaire Santé RPPS", "Doctors;Dentists;Pharmacists;Nurses;Other Professionals", "https://annuaire.sante.fr/", "Healthcare Professional Directory", "Search", False),
    ("de_baek", "Germany", "Medical Chamber Physician Directories", "Doctors", "https://www.bundesaerztekammer.de/", "Medical Directory", "Search", False),
    ("ch_medreg", "Switzerland", "MedReg", "Doctors;Dentists;Pharmacists;Chiropractors", "https://www.medregom.admin.ch/", "Healthcare Professional Register", "Search", False),
    ("no_hpr", "Norway", "HPR Register", "Doctors;Nurses;Dentists;Other Health Professionals", "https://www.helsedirektoratet.no/english/authorisation-and-license-for-health-personnel", "HPR Professional Register", "Search", False),
    ("fi_julkiterhikki", "Finland", "JulkiTerhikki", "Healthcare Professionals", "https://julkiterhikki.valvira.fi/", "Professional Register", "Search", False),
    ("dk_autor", "Denmark", "Authorisation Register", "Doctors;Dentists;Nurses;Other Health Professionals", "https://autregweb.sst.dk/", "Professional Register", "Search", False),
    ("se_hosp", "Sweden", "HOSP Register", "Licensed Healthcare Professionals", "https://www.socialstyrelsen.se/en/statistics-and-data/register/", "Professional Register", "Search", False),
    ("nl_zorgkaart", "Netherlands", "Healthcare Provider Directory", "Healthcare Professionals", "https://www.zorgkaartnederland.nl/", "Healthcare Directory", "Web", False),
    ("in_practo", "India", "Practo", "Doctors;Dentists;Other Healthcare Professionals", "https://www.practo.com/", "Healthcare Directory", "Web", False),
    ("in_1mg", "India", "1mg Doctors", "Doctors;Dentists;Other Healthcare Professionals", "https://www.1mg.com/doctors", "Healthcare Directory", "Web", False),
    ("in_justdial", "India", "Justdial Healthcare", "Doctors;Dentists;Clinics;Hospitals", "https://www.justdial.com/", "Business/Healthcare Directory", "Web", False),
    ("in_google_maps", "India", "Google Maps Business Profiles", "Doctors;Dentists;Clinics;Hospitals", "https://www.google.com/maps/", "Business Directory", "Web/API", True),
    ("hospital_websites", "India", "Hospital Websites", "Healthcare Professionals", "", "Hospital Directory", "Web", True),
    ("who_gho", "Global", "WHO Global Health Observatory", "Health Workforce", "https://www.who.int/data/gho", "Health Workforce Dataset", "Download", True),
    ("who_nhwa", "Global", "WHO National Health Workforce Accounts", "Health Professionals", "https://www.who.int/teams/health-workforce/nhwa", "Health Workforce Dataset", "Download", True),
    ("iamra", "Global", "IAMRA Public Registers", "Medical Professionals", "https://www.iamra.net/public-registers-resource/", "Medical Regulatory Directory", "Directory", True),
    ("web_search", "Global", "Public web search", "Periodontists listed on public clinic pages", "", "Web crawl", "HTML", False),
]


def _is_dental(profession: str) -> bool:
    blob = (profession or "").lower()
    tokens = ("dentist", "dental", "periodont", "clinic", "hospital", "healthcare provider", "nppes", "other healthcare")
    return any(token in blob for token in tokens)


def _as_registry(row: tuple) -> dict[str, Any]:
    item = dict(zip(COLUMNS, row))
    item["official_url"] = item["webpage"]
    item["professions"] = item["profession"]
    item["scrape_mode"] = "html"
    item["dental_relevant"] = _is_dental(item["profession"]) or item["id"] in {"npi", "web_search"}
    item["regulator"] = item["registry"]
    item["api_or_bulk"] = item["extraction_method"]
    return item


REGISTRIES: list[dict[str, Any]] = [_as_registry(row) for row in _ROWS]
ALIASES = {
    "npi_registry": "npi",
    "nppes": "npi",
    "uk_gdc_register": "uk_gdc",
    "au_dental": "au_dental_board",
}


def get_registry(registry_id: str) -> dict[str, Any] | None:
    rid = ALIASES.get((registry_id or "").strip().lower(), (registry_id or "").strip().lower())
    for item in REGISTRIES:
        if item["id"] == rid:
            return item
    return None


def dental_registries() -> list[dict[str, Any]]:
    return [item for item in REGISTRIES if item.get("dental_relevant")]


def scrapeable_registries(dental_only: bool = True) -> list[dict[str, Any]]:
    rows = dental_registries() if dental_only else REGISTRIES
    return [
        item
        for item in rows
        if item.get("webpage") and not item.get("skip_auto") and item["id"] != "web_search"
    ]


def implemented_api_registries() -> list[dict[str, Any]]:
    return [item for item in REGISTRIES if item["id"] == "npi"]


def registry_host(item: dict[str, Any]) -> str:
    return urlparse(item.get("webpage") or "").netloc.lower()
