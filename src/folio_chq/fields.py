"""Item-level fields available to the items CSV and the embedded MARC item field."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .dates import latest, norm

# field name -> description (shown by `folio-chq fields`)
ITEM_FIELDS: dict[str, str] = {
    "instance_id": "FOLIO instance UUID (also in MARC 999 ff $i)",
    "instance_hrid": "Instance HRID; equals MARC 001, the bib-to-item link",
    "title": "Instance title",
    "holdings_hrid": "Holdings record HRID",
    "item_id": "FOLIO item UUID",
    "item_hrid": "Item HRID",
    "barcode": "Item barcode",
    "material_type": "Material type name",
    "loan_type": "Permanent loan type name",
    "status": "Item status (Available, Checked out, Missing, ...)",
    "status_date": "Date the item status last changed",
    "due_date": "Due date of the open loan, if checked out",
    "last_circ_date": "Last checkout date (or latest circ activity, see extract.last_circ_date_from)",
    "last_checkout_date": "Most recent loan start date recorded in FOLIO (or legacy value)",
    "last_checkin_date": "Most recent check-in (item.lastCheckIn)",
    "loans_total": "Checkouts recorded in FOLIO plus legacy count, if configured",
    "loans_folio": "Checkouts recorded in FOLIO only",
    "loans_window": "Checkouts in the last N months (extract.loan_window_months)",
    "renewals_total": "Renewals across all FOLIO loans",
    "legacy_circ_count": "Circulation count carried over from the previous system",
    "created_date": "Item created date (legacy value if configured, else FOLIO record creation)",
    "location_code": "Effective location code",
    "location_name": "Effective location name",
    "library_code": "Library code of the effective location",
    "library_name": "Library name of the effective location",
    "campus_code": "Campus code",
    "campus_name": "Campus name",
    "institution_code": "Institution code",
    "institution_name": "Institution name",
    "permanent_location_code": "Permanent (home) location code",
    "call_number": "Effective call number with prefix and suffix",
    "call_number_bare": "Effective call number without prefix/suffix",
    "call_number_full": "Call number plus volume, enumeration, chronology and copy",
    "call_number_prefix": "Call number prefix",
    "call_number_suffix": "Call number suffix",
    "call_number_type": "Call number type (e.g. Library of Congress classification)",
    "volume": "Volume",
    "enumeration": "Enumeration",
    "chronology": "Chronology",
    "copy_number": "Copy number",
    "item_suppressed": "Item suppressed from discovery (Y/N)",
    "instance_suppressed": "Instance suppressed (Y/N)",
}

DATE_FIELDS = {"status_date", "due_date", "last_circ_date", "last_checkout_date", "last_checkin_date", "created_date"}


@dataclass
class Ref:
    locations: dict
    libraries: dict
    campuses: dict
    institutions: dict
    material_types: dict
    loan_types: dict
    call_number_types: dict
    item_note_types: dict
    identifier_types: dict
    classification_types: dict

    @classmethod
    def from_cache(cls, cache) -> Ref:
        return cls(**{k: cache.refdata(k) for k in cls.__dataclass_fields__})

    def note_type_id(self, name: str | None) -> str | None:
        if not name:
            return None
        for i, t in self.item_note_types.items():
            if t.get("name", "").strip().lower() == name.strip().lower():
                return i
        raise ValueError(f"Item note type {name!r} not found in FOLIO (check the legacy: settings)")


def _name(table: dict, id_: str | None, attr: str = "name") -> str:
    return (table.get(id_) or {}).get(attr, "") if id_ else ""


def _join(*parts: Any) -> str:
    return " ".join(str(p).strip() for p in parts if p and str(p).strip())


def _note(item: dict, type_id: str | None) -> str | None:
    if not type_id:
        return None
    for n in item.get("notes") or []:
        if n.get("itemNoteTypeId") == type_id and n.get("note"):
            return str(n["note"]).strip()
    return None


def _int(value: str | None) -> int:
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return 0


class RowBuilder:
    def __init__(self, ref: Ref, cfg: dict) -> None:
        self.ref = ref
        self.any_activity = cfg["extract"]["last_circ_date_from"] == "any"
        from zoneinfo import ZoneInfo

        # Legacy values are usually plain dates in local time, e.g. "1998-03-15".
        self.local_tz = ZoneInfo(cfg["output"]["items_csv"].get("timezone") or "UTC")
        leg = cfg["legacy"]
        self.legacy_created = ref.note_type_id(leg.get("created_date_note_type"))
        self.legacy_count = ref.note_type_id(leg.get("circ_count_note_type"))
        self.legacy_last = ref.note_type_id(leg.get("last_circ_date_note_type"))

    def build(self, item: dict, holdings: dict, instance: dict, loans: dict) -> dict:
        ref = self.ref
        loc_id = item.get("effectiveLocationId")
        loc = ref.locations.get(loc_id) or {}
        cn = item.get("effectiveCallNumberComponents") or {}
        status = item.get("status") or {}

        legacy_count = _int(_note(item, self.legacy_count)) if self.legacy_count else 0
        legacy_last = norm(_note(item, self.legacy_last), self.local_tz) if self.legacy_last else None
        legacy_created = norm(_note(item, self.legacy_created), self.local_tz) if self.legacy_created else None

        last_checkout = latest(loans.get("last_loan"), legacy_last)
        last_checkin = norm((item.get("lastCheckIn") or {}).get("dateTime"))
        last_circ = latest(last_checkout, last_checkin, loans.get("last_return")) if self.any_activity else last_checkout
        folio_loans = int(loans.get("total") or 0)

        call_number = _join(cn.get("prefix"), cn.get("callNumber"), cn.get("suffix"))
        copy = item.get("copyNumber")
        return {
            "instance_id": instance.get("id", ""),
            "instance_hrid": instance.get("hrid", ""),
            "title": instance.get("title", ""),
            "holdings_hrid": holdings.get("hrid", ""),
            "item_id": item.get("id", ""),
            "item_hrid": item.get("hrid", ""),
            "barcode": item.get("barcode") or "",
            "material_type": _name(ref.material_types, item.get("materialTypeId")),
            "loan_type": _name(ref.loan_types, item.get("permanentLoanTypeId")),
            "status": status.get("name", ""),
            "status_date": norm(status.get("date")),
            "due_date": loans.get("open_due") if status.get("name") != "Available" else None,
            "last_circ_date": last_circ,
            "last_checkout_date": last_checkout,
            "last_checkin_date": last_checkin,
            "loans_total": folio_loans + legacy_count,
            "loans_folio": folio_loans,
            "loans_window": int(loans.get("window") or 0),
            "renewals_total": int(loans.get("renewals") or 0),
            "legacy_circ_count": legacy_count if self.legacy_count else "",
            "created_date": legacy_created or norm((item.get("metadata") or {}).get("createdDate")),
            "location_code": loc.get("code", ""),
            "location_name": loc.get("discoveryDisplayName") or loc.get("name", ""),
            "library_code": _name(ref.libraries, loc.get("libraryId"), "code"),
            "library_name": _name(ref.libraries, loc.get("libraryId")),
            "campus_code": _name(ref.campuses, loc.get("campusId"), "code"),
            "campus_name": _name(ref.campuses, loc.get("campusId")),
            "institution_code": _name(ref.institutions, loc.get("institutionId"), "code"),
            "institution_name": _name(ref.institutions, loc.get("institutionId")),
            "permanent_location_code": _name(
                ref.locations, item.get("permanentLocationId") or holdings.get("permanentLocationId"), "code"
            ),
            "call_number": call_number,
            "call_number_bare": cn.get("callNumber", "") or "",
            "call_number_full": _join(
                call_number,
                item.get("volume"),
                item.get("enumeration"),
                item.get("chronology"),
                f"c.{copy}" if copy else None,
            ),
            "call_number_prefix": cn.get("prefix", "") or "",
            "call_number_suffix": cn.get("suffix", "") or "",
            "call_number_type": _name(ref.call_number_types, cn.get("typeId")),
            "volume": item.get("volume") or "",
            "enumeration": item.get("enumeration") or "",
            "chronology": item.get("chronology") or "",
            "copy_number": copy or "",
            "item_suppressed": "Y" if item.get("discoverySuppress") else "N",
            "instance_suppressed": "Y" if instance.get("discoverySuppress") or instance.get("staffSuppress") else "N",
        }
