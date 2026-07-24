from __future__ import annotations

import csv
import dataclasses
import io
import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.auth.core import get_current_user
from app.models.database import ConversionJob, User, get_db
from app.models.schemas import (
    JobOut, JobListItemOut, UploadResponse, VendorInfo, ParseResponse, DetectedInterfaceOut,
    MappingSubmission, MappingResponse, MappingValidationOut, MappingIssueOut,
    ConfigSummaryOut, ConversionIssueOut,
    ObjectRowsOut, ObjectRowsIn, ObjectRowsSaveOut, EDITABLE_CATEGORIES,
    ValidationOut, ExportSectionsIn, ExportPreviewOut,
    ProfilesOut, ProfilesIn,
    CleanupFindingOut, CleanupOut, CleanupDeleteIn,
)
from app.normalizer.models import NormalizedConfig, ConversionIssue
from app.normalizer.serialization import (
    config_to_dict, config_from_dict, get_category_rows, set_category_rows, sync_zones_and_interfaces,
)
from app.parsers.registry import list_vendors, get_parser_class
from app.generators.paloalto.generator import PaloAltoGenerator
from app.mapping.apply import InterfaceMappingEntry, validate_mapping, apply_mapping
from app.mapping.defaults import build_default_mapping
from app.reports.summary import build_summary
from app.reports.excel_export import build_summary_workbook
from app.validation.engine import validate_config
from app.validation.cleanup import find_cleanup_issues

logger = logging.getLogger("api.routes")
router = APIRouter(prefix=settings.api_prefix)


@router.get("/vendors", response_model=list[VendorInfo])
def get_vendors():
    """List vendors currently supported by a registered parser."""
    return list_vendors()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/jobs", response_model=list[JobListItemOut])
def list_jobs(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Job history for the home screen: most recent first, scoped to the
    signed-in user only. Lightweight - no stats/issues payload (use
    GET /jobs/{id} for the full record when the user actually resumes one).
    """
    jobs = (
        db.query(ConversionJob)
        .filter(ConversionJob.user_id == current_user.id)
        .order_by(ConversionJob.created_at.desc())
        .limit(200)
        .all()
    )
    return jobs


def _job_to_out(job: ConversionJob) -> JobOut:
    return JobOut(
        id=job.id,
        job_name=job.job_name,
        vendor=job.vendor,
        original_filename=job.original_filename,
        status=job.status,
        created_at=job.created_at,
        completed_at=job.completed_at,
        stats=job.stats_json,
        issues=job.issues_json or [],
        error_message=job.error_message,
    )


def _enforce_job_quota(user: User, db: Session) -> None:
    """Free plan: capped at settings.free_plan_job_limit total saved jobs.
    Pro plan: unlimited. This is a placeholder tier model - swap for real
    Stripe-subscription-driven limits once billing exists."""
    if user.plan == "pro":
        return
    count = db.query(ConversionJob).filter(ConversionJob.user_id == user.id).count()
    if count >= settings.free_plan_job_limit:
        raise HTTPException(
            402,
            f"Free plan limit reached ({settings.free_plan_job_limit} saved jobs). "
            f"Delete an old job or upgrade to continue.",
        )


async def _read_upload(file: UploadFile) -> str:
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.max_upload_mb:
        raise HTTPException(413, f"File exceeds {settings.max_upload_mb} MB limit ({size_mb:.1f} MB)")
    try:
        return contents.decode("utf-8")
    except UnicodeDecodeError:
        logger.warning("File %s was not valid UTF-8, decoded as latin-1", file.filename)
        return contents.decode("latin-1", errors="replace")


def _run_parser(vendor: str, text: str, filename: str) -> NormalizedConfig | None:
    parser_cls = get_parser_class(vendor)
    if parser_cls is None:
        return None
    parser = parser_cls(raw_text=text, filename=filename)
    return parser.parse()


def _generate_and_store(job: ConversionJob, config: NormalizedConfig, db: Session) -> None:
    """Runs the PAN-OS generator against an already-mapped config, writes
    output artifacts, and marks the job completed. Shared by both the
    legacy one-shot /convert path and the wizard's /mapping endpoint."""
    generator = PaloAltoGenerator(config)
    cli_text = generator.generate_all()

    outputs_base = settings.outputs_dir / job.id
    outputs_base.mkdir(parents=True, exist_ok=True)

    cli_path = outputs_base / "paloalto_config.txt"
    cli_path.write_text(cli_text, encoding="utf-8")

    json_path = outputs_base / "normalized_config.json"
    json_path.write_text(json.dumps({**config_to_dict(config), "stats": config.stats()}, indent=2, default=str), encoding="utf-8")

    csv_path = outputs_base / "objects_summary.csv"
    _write_csv_summary(config, csv_path)

    job.status = "completed"
    job.stats_json = config.stats()
    job.issues_json = [dataclasses.asdict(i) for i in config.issues]
    job.cli_output_path = str(cli_path)
    job.json_output_path = str(json_path)
    job.csv_output_path = str(csv_path)
    db.commit()


# --- Legacy one-shot path (no interface mapping wizard) --------------------
@router.post("/convert", response_model=UploadResponse)
async def convert_config(
    vendor: str = Form(...),
    file: UploadFile = File(...),
    job_name: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Quick/convenience path: parse and generate in one call using an
    auto-assigned default interface mapping (sequential ethernet1/N,
    zone = the parser's suggested zone). This is lower-fidelity than the
    interface mapping wizard (POST /parse then POST /jobs/{id}/mapping)
    by design - PAN-OS is zone-based and this vendor config is interface-
    based, so an automatic mapping is always a guess. Use this for quick
    testing; use the wizard for anything you intend to actually deploy.
    """
    _enforce_job_quota(current_user, db)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix and suffix not in settings.allowed_extensions:
        logger.warning("Rejected upload with extension %s", suffix)

    text = await _read_upload(file)

    job_id = str(uuid.uuid4())
    job = ConversionJob(id=job_id, user_id=current_user.id, job_name=job_name, vendor=vendor, original_filename=file.filename or "config.txt", status="parsing")
    db.add(job)
    db.commit()

    upload_path = settings.uploads_dir / f"{job_id}_{Path(file.filename or 'config.txt').name}"
    upload_path.write_text(text, encoding="utf-8")

    normalized = _run_parser(vendor, text, file.filename or "")
    if normalized is None:
        job.status = "failed"
        job.error_message = (
            f"No parser registered for vendor '{vendor}' yet. "
            f"Currently registered: {[v['key'] for v in list_vendors()] or 'none'}"
        )
        db.commit()
        return UploadResponse(job=_job_to_out(job), message=job.error_message)

    try:
        default_mapping = build_default_mapping(normalized)
        apply_mapping(normalized, default_mapping)
        _generate_and_store(job, normalized, db)
        return UploadResponse(job=_job_to_out(job), message="Conversion completed (auto-mapped - review zone assignments).")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Conversion failed for job %s", job_id)
        job.status = "failed"
        job.error_message = str(exc)
        db.commit()
        return UploadResponse(job=_job_to_out(job), message=f"Conversion failed: {exc}")


# --- Interface mapping wizard: phase 1, parse only --------------------------
@router.post("/parse", response_model=ParseResponse)
async def parse_config(
    vendor: str = Form(...),
    file: UploadFile = File(...),
    job_name: str | None = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Parses the uploaded config and stops - no CLI is generated yet. Returns
    the detected interfaces for the mapping wizard's first screen. The
    parsed config is persisted on the job row so POST /jobs/{id}/mapping
    can pick it up once the user confirms their interface mapping.
    """
    _enforce_job_quota(current_user, db)
    text = await _read_upload(file)

    job_id = str(uuid.uuid4())
    job = ConversionJob(id=job_id, user_id=current_user.id, job_name=job_name, vendor=vendor, original_filename=file.filename or "config.txt", status="parsing")
    db.add(job)
    db.commit()

    upload_path = settings.uploads_dir / f"{job_id}_{Path(file.filename or 'config.txt').name}"
    upload_path.write_text(text, encoding="utf-8")

    normalized = _run_parser(vendor, text, file.filename or "")
    if normalized is None:
        job.status = "failed"
        job.error_message = (
            f"No parser registered for vendor '{vendor}' yet. "
            f"Currently registered: {[v['key'] for v in list_vendors()] or 'none'}"
        )
        db.commit()
        return ParseResponse(job=_job_to_out(job), interfaces=[], message=job.error_message)

    job.status = "awaiting_mapping"
    job.normalized_config_json = config_to_dict(normalized)
    job.stats_json = normalized.stats()
    job.issues_json = [dataclasses.asdict(i) for i in normalized.issues]
    db.commit()

    interfaces_out = [
        DetectedInterfaceOut(
            source_interface=i.name,
            hardware_name=i.hardware_name,
            suggested_zone=i.zone,
            ip_address=i.ip_address,
            netmask=i.netmask,
            description=i.description,
            mtu=i.mtu,
            virtual_router=i.virtual_router,
        )
        for i in normalized.interfaces
    ]
    return ParseResponse(job=_job_to_out(job), interfaces=interfaces_out, message="Parsed - confirm interface mapping before generating.")


@router.get("/jobs/{job_id}/interfaces", response_model=list[DetectedInterfaceOut])
def get_job_interfaces(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _require_job_with_config(job_id, current_user, db)
    config = config_from_dict(job.normalized_config_json)
    return [
        DetectedInterfaceOut(
            source_interface=i.name, hardware_name=i.hardware_name, suggested_zone=i.zone,
            ip_address=i.ip_address, netmask=i.netmask, description=i.description,
            mtu=i.mtu, virtual_router=i.virtual_router,
        )
        for i in config.interfaces
    ]


def _require_job_with_config(job_id: str, user: User, db: Session) -> ConversionJob:
    job = db.get(ConversionJob, job_id)
    # 404 (not 403) when the job belongs to someone else - don't confirm
    # that a given job_id exists to a user who isn't allowed to see it.
    if not job or job.user_id != user.id:
        raise HTTPException(404, "Job not found")
    if not job.normalized_config_json:
        raise HTTPException(409, "Job has no parsed config available")
    return job


@router.get("/jobs/{job_id}/summary", response_model=ConfigSummaryOut)
def get_job_summary(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Full inventory of what was parsed from the uploaded file: counts plus
    the actual object rows (name/value/etc.) for addresses, address
    groups, services, service groups, interfaces, routes, policies, and
    NAT rules. Available as soon as /parse completes, independent of
    whether interface mapping has happened yet.
    """
    job = _require_job_with_config(job_id, current_user, db)
    config = config_from_dict(job.normalized_config_json)
    return build_summary(config)


# --- Editable object grids (Address Objects, Groups, Services, etc.) -------
@router.get("/jobs/{job_id}/objects/{category}", response_model=ObjectRowsOut)
def get_job_objects(job_id: str, category: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Raw editable rows for one object category, for the grid to load."""
    if category not in EDITABLE_CATEGORIES:
        raise HTTPException(400, f"category must be one of: {', '.join(EDITABLE_CATEGORIES)}")
    job = _require_job_with_config(job_id, current_user, db)
    config = config_from_dict(job.normalized_config_json)
    return ObjectRowsOut(category=category, rows=get_category_rows(config, category))


@router.put("/jobs/{job_id}/objects/{category}", response_model=ObjectRowsSaveOut)
def put_job_objects(job_id: str, category: str, payload: ObjectRowsIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Replaces the entire row set for one object category with what the grid
    sends back - the simplest contract that still supports add/edit/delete
    /reorder from a single autosave call. Re-runs live validation and
    updates the job's stored stats/issues immediately, so the Validation
    Center and stat counters reflect the edit without a re-upload.
    """
    if category not in EDITABLE_CATEGORIES:
        raise HTTPException(400, f"category must be one of: {', '.join(EDITABLE_CATEGORIES)}")
    job = _require_job_with_config(job_id, current_user, db)
    config = config_from_dict(job.normalized_config_json)

    try:
        set_category_rows(config, category, payload.rows)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(400, f"Invalid row data for '{category}': {exc}")

    sync_warnings: list[tuple[str, str]] = []
    if category in ("zones", "interfaces"):
        sync_warnings = sync_zones_and_interfaces(config, category)

    issues = validate_config(config)
    for iface_name, msg in sync_warnings:
        issues.append(ConversionIssue("warning", "interface", iface_name, msg))
    config.issues = issues
    job.normalized_config_json = config_to_dict(config)
    job.stats_json = config.stats()
    job.issues_json = [dataclasses.asdict(i) for i in issues]
    db.commit()

    return ObjectRowsSaveOut(
        category=category,
        rows=get_category_rows(config, category),
        issues=[ConversionIssueOut(**dataclasses.asdict(i)) for i in issues],
        stats=config.stats(),
    )


# --- Validation Center -------------------------------------------------------
@router.get("/jobs/{job_id}/cleanup", response_model=CleanupOut)
def get_job_cleanup(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Configuration Cleanup findings: unused objects, empty groups, and
    duplicate-value objects - recomputed live from the current config,
    same "always re-check, never stale" pattern as the Validation Center.
    """
    job = _require_job_with_config(job_id, current_user, db)
    config = config_from_dict(job.normalized_config_json)
    findings = find_cleanup_issues(config)
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.category] = counts.get(f.category, 0) + 1
    return CleanupOut(
        findings=[CleanupFindingOut(category=f.category, object_type=f.object_type, name=f.name,
                                     message=f.message, related=f.related) for f in findings],
        counts=counts,
    )


@router.post("/jobs/{job_id}/cleanup/delete", response_model=CleanupOut)
def delete_cleanup_objects(job_id: str, body: CleanupDeleteIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Deletes the named objects from the given category (as flagged by
    GET /cleanup) and returns the refreshed findings."""
    if body.object_type not in EDITABLE_CATEGORIES:
        raise HTTPException(400, f"object_type must be one of: {', '.join(EDITABLE_CATEGORIES)}")
    job = _require_job_with_config(job_id, current_user, db)
    config = config_from_dict(job.normalized_config_json)

    rows = get_category_rows(config, body.object_type)
    names_to_delete = set(body.names)
    remaining = [r for r in rows if r["name"] not in names_to_delete]
    set_category_rows(config, body.object_type, remaining)

    issues = validate_config(config)
    config.issues = issues
    job.normalized_config_json = config_to_dict(config)
    job.stats_json = config.stats()
    job.issues_json = [dataclasses.asdict(i) for i in issues]
    db.commit()

    findings = find_cleanup_issues(config)
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.category] = counts.get(f.category, 0) + 1
    return CleanupOut(
        findings=[CleanupFindingOut(category=f.category, object_type=f.object_type, name=f.name,
                                     message=f.message, related=f.related) for f in findings],
        counts=counts,
    )


@router.get("/jobs/{job_id}/cleanup/report")
def download_cleanup_report(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Downloads the current cleanup findings as a CSV report."""
    job = _require_job_with_config(job_id, current_user, db)
    config = config_from_dict(job.normalized_config_json)
    findings = find_cleanup_issues(config)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Category", "Object Type", "Name", "Message", "Related Objects"])
    for f in findings:
        writer.writerow([f.category, f.object_type, f.name, f.message, "; ".join(f.related)])

    outputs_base = settings.outputs_dir / job.id
    outputs_base.mkdir(parents=True, exist_ok=True)
    out_path = outputs_base / "cleanup_report.csv"
    out_path.write_text(buffer.getvalue(), encoding="utf-8")

    return FileResponse(
        out_path, media_type="text/csv",
        filename=f"{Path(job.original_filename).stem}_cleanup_report.csv",
    )


@router.get("/jobs/{job_id}/profiles", response_model=ProfilesOut)
def get_job_profiles(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Named Log Forwarding Profiles / Security Profile Groups for this job.
    These are just NAMES (the profiles themselves already exist on the
    destination firewall) - Security Policy rows reference one of these
    names via a dropdown instead of free-typing it.
    """
    job = _require_job_with_config(job_id, current_user, db)
    config = config_from_dict(job.normalized_config_json)
    return ProfilesOut(
        log_forwarding_profiles=config.log_forwarding_profiles,
        security_profile_groups=config.security_profile_groups,
    )


@router.put("/jobs/{job_id}/profiles", response_model=ProfilesOut)
def put_job_profiles(job_id: str, body: ProfilesIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = _require_job_with_config(job_id, current_user, db)
    config = config_from_dict(job.normalized_config_json)

    # De-dupe while preserving order, drop blanks
    def _clean(names: list[str]) -> list[str]:
        seen: set[str] = set()
        out = []
        for n in names:
            n = n.strip()
            if n and n not in seen:
                seen.add(n)
                out.append(n)
        return out

    config.log_forwarding_profiles = _clean(body.log_forwarding_profiles)
    config.security_profile_groups = _clean(body.security_profile_groups)

    job.normalized_config_json = config_to_dict(config)
    db.commit()
    return ProfilesOut(
        log_forwarding_profiles=config.log_forwarding_profiles,
        security_profile_groups=config.security_profile_groups,
    )


@router.get("/jobs/{job_id}/validation", response_model=ValidationOut)
def get_job_validation(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Live validation of the CURRENT config (including any grid edits made
    so far) - recomputed on every call so the Validation Center always
    matches what's actually in the job right now, not a parse-time
    snapshot.
    """
    job = _require_job_with_config(job_id, current_user, db)
    config = config_from_dict(job.normalized_config_json)
    issues = validate_config(config)
    job.issues_json = [dataclasses.asdict(i) for i in issues]
    job.stats_json = config.stats()
    db.commit()
    return ValidationOut(
        issues=[ConversionIssueOut(**dataclasses.asdict(i)) for i in issues],
        stats=config.stats(),
    )


# --- Selective export (choose exactly which CLI sections to generate) ------
@router.post("/jobs/{job_id}/export/preview", response_model=ExportPreviewOut)
def export_preview(job_id: str, body: ExportSectionsIn, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Generates CLI text for just the requested sections (or everything, if
    sections is omitted/["all"]) and returns it for the Preview screen -
    nothing is written to disk here."""
    job = _require_job_with_config(job_id, current_user, db)
    config = config_from_dict(job.normalized_config_json)
    generator = PaloAltoGenerator(config)
    cli_text = generator.generate_selected(body.sections)
    command_count = sum(1 for line in cli_text.splitlines() if line.strip() and not line.strip().startswith("#"))
    used_sections = (
        list(PaloAltoGenerator.SECTION_METHODS.keys())
        if not body.sections or "all" in body.sections
        else [s for s in PaloAltoGenerator.SECTION_METHODS if s in body.sections]
    )
    return ExportPreviewOut(cli=cli_text, command_count=command_count, sections=used_sections)


@router.get("/jobs/{job_id}/export/download")
def export_selected_download(job_id: str, sections: str = "all", current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Same generation as /export/preview, but writes the file and returns
    it as a download. `sections` is a comma-separated list of section keys,
    or the literal 'all'."""
    job = _require_job_with_config(job_id, current_user, db)
    config = config_from_dict(job.normalized_config_json)
    generator = PaloAltoGenerator(config)
    section_list = None if sections == "all" else [s for s in sections.split(",") if s]
    cli_text = generator.generate_selected(section_list)

    outputs_base = settings.outputs_dir / job.id
    outputs_base.mkdir(parents=True, exist_ok=True)
    out_path = outputs_base / "paloalto_selected_export.txt"
    out_path.write_text(cli_text, encoding="utf-8")

    return FileResponse(
        out_path, media_type="text/plain",
        filename=f"{Path(job.original_filename).stem}_paloalto_selected.txt",
    )


@router.get("/jobs/{job_id}/export/excel")
def export_summary_excel(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Downloads the configuration summary (counts + full object tables) as an .xlsx workbook."""
    job = _require_job_with_config(job_id, current_user, db)
    config = config_from_dict(job.normalized_config_json)
    wb = build_summary_workbook(config, vendor=job.vendor, source_filename=job.original_filename)

    outputs_base = settings.outputs_dir / job.id
    outputs_base.mkdir(parents=True, exist_ok=True)
    xlsx_path = outputs_base / "configuration_summary.xlsx"
    wb.save(xlsx_path)

    return FileResponse(
        xlsx_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{Path(job.original_filename).stem}_summary.xlsx",
    )


# --- Interface mapping wizard: phase 2, confirm mapping + generate ----------
@router.post("/jobs/{job_id}/mapping", response_model=MappingResponse)
def submit_mapping(job_id: str, submission: MappingSubmission, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Applies the user-confirmed interface mapping to the parsed config and
    generates the PAN-OS CLI. Validation runs first; if there are blocking
    errors (or the caller passed validate_only=true), generation is
    skipped and the validation result is returned instead.
    """
    job = db.get(ConversionJob, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")
    if not job.normalized_config_json:
        raise HTTPException(409, "Job has no parsed config to apply a mapping to - call /parse first")

    config = config_from_dict(job.normalized_config_json)
    mappings = [InterfaceMappingEntry(**m.model_dump()) for m in submission.mappings]

    result = validate_mapping(config, mappings)
    validation_out = MappingValidationOut(
        blocking=result.blocking,
        issues=[MappingIssueOut(severity=i.severity, object_type=i.object_type,
                                 object_name=i.object_name, message=i.message) for i in result.issues],
    )

    if result.blocking or submission.validate_only:
        job.interface_mapping_json = [m.model_dump() for m in submission.mappings]
        db.commit()
        msg = "Validation errors must be resolved before generating." if result.blocking else "Validation passed."
        return MappingResponse(job=_job_to_out(job), validation=validation_out, message=msg)

    try:
        apply_mapping(config, mappings)
        job.interface_mapping_json = [m.model_dump() for m in submission.mappings]
        # apply_mapping() resolves raw vendor interface/zone names (e.g. a
        # FortiGate NAT rule's dstintf "wan1", used for the NAT interface
        # dropdown's "interface:<pan_name>" marker) into real PAN-OS
        # values purely in-memory. Without writing that back here, every
        # editable-grid read (GET /objects/interfaces, /objects/nat_rules,
        # ...) kept decoding the pre-mapping snapshot forever - pan_name
        # stayed blank and the NAT Translated Source dropdown had nothing
        # to offer, even though the generated CLI file was correct.
        job.normalized_config_json = config_to_dict(config)
        _generate_and_store(job, config, db)
        return MappingResponse(job=_job_to_out(job), validation=validation_out, message="Mapping applied, configuration generated.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Generation failed for job %s after mapping", job_id)
        job.status = "failed"
        job.error_message = str(exc)
        db.commit()
        return MappingResponse(job=_job_to_out(job), validation=validation_out, message=f"Generation failed: {exc}")


@router.post("/jobs/{job_id}/generate", response_model=MappingResponse)
def generate_from_overview(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Generates the PAN-OS CLI directly from whatever is currently in the
    Interfaces grid (pan_name/zone/virtual_router/interface_type per row) -
    no separate mapping-wizard submission required. Internally this is the
    exact same validate_mapping/apply_mapping pipeline the older /mapping
    endpoint uses (kept for backward compatibility), just with the mapping
    entries derived from config.interfaces instead of a request body.
    """
    job = db.get(ConversionJob, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")
    if not job.normalized_config_json:
        raise HTTPException(409, "Job has no parsed config to generate from - call /parse first")

    config = config_from_dict(job.normalized_config_json)
    mappings = [
        InterfaceMappingEntry(
            source_interface=i.name,
            pan_interface=i.pan_name or "",
            zone=i.zone or "",
            virtual_router=i.virtual_router or "default",
            interface_type=i.interface_type or "layer3",
            ip_address=i.ip_address,
            netmask=i.netmask,
            description=i.description or "",
            enabled=i.enabled,
        )
        for i in config.interfaces
    ]

    result = validate_mapping(config, mappings)

    # Interface-mapping issues alone aren't the whole picture - invalid
    # names, dangling group members, malformed IPs, etc. from the live
    # Validation Center engine should also block generation, not just be
    # visible after the fact in an already-exported file.
    config_issues = validate_config(config)
    blocking_config_issues = [i for i in config_issues if i.severity == "error"]
    all_issues = result.issues + blocking_config_issues

    validation_out = MappingValidationOut(
        blocking=result.blocking or len(blocking_config_issues) > 0,
        issues=[MappingIssueOut(severity=i.severity, object_type=i.object_type,
                                 object_name=i.object_name, message=i.message) for i in all_issues],
    )

    if validation_out.blocking:
        return MappingResponse(
            job=_job_to_out(job), validation=validation_out,
            message="Fix the flagged errors below before generating - check the Validation Center for full details.",
        )

    try:
        apply_mapping(config, mappings)
        job.interface_mapping_json = [m.__dict__ for m in mappings]
        # See the matching comment in submit_mapping() above - without this,
        # NAT/Policy/Route rows that reference a raw vendor interface or
        # zone name never picked up their resolved PAN-OS equivalent in the
        # editable grids, only in the one-off generated CLI file.
        job.normalized_config_json = config_to_dict(config)
        _generate_and_store(job, config, db)
        return MappingResponse(job=_job_to_out(job), validation=validation_out, message="Configuration generated.")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Generation failed for job %s", job_id)
        job.status = "failed"
        job.error_message = str(exc)
        db.commit()
        return MappingResponse(job=_job_to_out(job), validation=validation_out, message=f"Generation failed: {exc}")


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(ConversionJob, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")
    return _job_to_out(job)


@router.delete("/jobs/{job_id}", status_code=204)
def delete_job(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Deletes a job and any generated output files on disk. Uploaded
    source config text isn't retained separately (only the parsed
    normalized_config_json on the row itself), so removing the row is
    enough to fully forget it."""
    job = db.get(ConversionJob, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")

    outputs_dir = settings.outputs_dir / job.id
    if outputs_dir.exists():
        import shutil
        shutil.rmtree(outputs_dir, ignore_errors=True)

    for upload in settings.uploads_dir.glob(f"{job.id}_*"):
        upload.unlink(missing_ok=True)

    db.delete(job)
    db.commit()
    return None


@router.get("/jobs/{job_id}/download/{artifact}")
def download_artifact(job_id: str, artifact: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = db.get(ConversionJob, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(404, "Job not found")

    path_map = {
        "cli": (job.cli_output_path, "paloalto_config.txt", "text/plain"),
        "csv": (job.csv_output_path, "objects_summary.csv", "text/csv"),
        "json": (job.json_output_path, "normalized_config.json", "application/json"),
    }
    if artifact not in path_map:
        raise HTTPException(400, "artifact must be one of: cli, csv, json")

    path_str, download_name, media_type = path_map[artifact]
    if not path_str or not Path(path_str).exists():
        raise HTTPException(404, "Artifact not available for this job")

    return FileResponse(path_str, media_type=media_type, filename=download_name)


# --- helpers ----------------------------------------------------------
def _write_csv_summary(config: NormalizedConfig, path: Path) -> None:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["object_type", "name", "detail"])
    for a in config.addresses:
        writer.writerow(["address", a.name, f"{a.type.value} {a.value}"])
    for g in config.address_groups:
        writer.writerow(["address-group", g.name, ";".join(g.members)])
    for s in config.services:
        writer.writerow(["service", s.name, f"{s.protocol.value} {s.dest_port or ''}"])
    for sg in config.service_groups:
        writer.writerow(["service-group", sg.name, ";".join(sg.members)])
    for i in config.interfaces:
        writer.writerow(["interface", i.name, f"{i.pan_name or ''} zone={i.zone or ''}"])
    for p in config.policies:
        writer.writerow(["policy", p.name, f"{p.action.value}"])
    for n in config.nat_rules:
        writer.writerow(["nat", n.name, f"{n.nat_type}"])
    path.write_text(buf.getvalue(), encoding="utf-8")
