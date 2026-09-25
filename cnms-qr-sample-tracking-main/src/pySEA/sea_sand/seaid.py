from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import argparse
import csv
import datetime as _dt
import re
import secrets
import uuid


# Crockford Base32 alphabet (no I, L, O, U)
CROCKFORD32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CROCKFORD32_SET = set(CROCKFORD32)

# Field lengths (sum = 26 characters, excluding separators)
ORG_LEN = 2
GRP_LEN = 2
INSTR_LEN = 5
ROLE_LEN = 2
DATE_LEN = 6   # YYMMDD
TIME_LEN = 6   # HHMMSS
RAND_LEN = 3   # RRR

# Allowed roles (exactly 2 chars)
# 00=base instrument reference
# E0=experimental data
# S0=simulated data event
# T0=evolving base twin
# TE=experimental twin state
# TS=simulated twin state
# A0=analysis state
# N0=undefined/unknown
# X0=extension/other
ALLOWED_ROLES = {"00", "E0", "S0", "T0", "TE", "TS", "A0", "N0", "X0"}

# Canonical formatting: dash-separated
# ORG(2)-GRP(2)-INSTR(5)-ROLE(2)-YYMMDD(6)-HHMMSS(6)-RRR(3)
ID_RE = re.compile(
    r"^[0-9A-HJ-KM-NP-TV-Z]{2}"
    r"-[0-9A-HJ-KM-NP-TV-Z]{2}"
    r"-[0-9A-HJ-KM-NP-TV-Z]{5}"
    r"-(?:00|E0|S0|T0|TE|TS|A0|N0|X0)"
    r"-\d{6}"
    r"-\d{6}"
    r"-[0-9A-HJ-KM-NP-TV-Z]{3}$"
)

# Pick a stable namespace UUID ONCE for your ecosystem and never change it.
# Replace this with your real pySEA namespace UUID.
PYSEA_NAMESPACE = uuid.UUID("01234567-89ab-cdef-0123-456789abcdef")

_DEFAULT_ORG_CSV_CANDIDATES = (
    Path(__file__).with_name("org_list.csv"),
)
_ORG_GRP_CACHE: Optional[set[tuple[str, str]]] = None


def _crockford_normalize(s: str) -> str:
    """
    Normalize arbitrary text into Crockford-compatible uppercase symbols.

    Parameters
    ----------
    s : str
        Raw field text.

    Returns
    -------
    str
        Uppercase alphanumeric string with `O -> 0` and `I/L -> 1`.

    Notes
    -----
    Non-alphanumeric characters are removed.
    """
    s = s.upper()
    out: list[str] = []
    for ch in s:
        if "A" <= ch <= "Z" or "0" <= ch <= "9":
            if ch == "O":
                out.append("0")
            elif ch in ("I", "L"):
                out.append("1")
            else:
                out.append(ch)
    return "".join(out)


def _to_crockford_fixed(s: str, length: int, pad: str = "0") -> str:
    """
    Normalize and clamp a token to a fixed Crockford Base32 length.

    Parameters
    ----------
    s : str
        Raw field text.
    length : int
        Target output length.
    pad : str, default="0"
        Right-padding character.

    Returns
    -------
    str
        Fixed-width Crockford-safe token.
    """
    s_norm = _crockford_normalize(s)
    filtered = "".join(ch for ch in s_norm if ch in CROCKFORD32_SET)
    return filtered[:length].ljust(length, pad)


def _rand_crockford(n: int = RAND_LEN) -> str:
    """
    Create a random Crockford Base32 token.

    Parameters
    ----------
    n : int, default=RAND_LEN
        Number of characters to generate.

    Returns
    -------
    str
        Random Crockford token.
    """
    return "".join(secrets.choice(CROCKFORD32) for _ in range(n))


def _resolve_org_csv_path(csv_path: Optional[Path | str] = None) -> Path:
    """
    Resolve the path to the organization-group abbreviation table.

    Parameters
    ----------
    csv_path : pathlib.Path | str, optional
        Explicit CSV path. When omitted, built-in candidate paths are checked.

    Returns
    -------
    pathlib.Path
        Resolved path to the organization-group CSV.

    Raises
    ------
    FileNotFoundError
        If no candidate file exists.
    """
    if csv_path is not None:
        resolved = Path(csv_path)
        if not resolved.exists():
            raise FileNotFoundError(f"Organization CSV not found: {resolved}")
        return resolved

    for candidate in _DEFAULT_ORG_CSV_CANDIDATES:
        if candidate.exists():
            return candidate

    candidates = ", ".join(str(p) for p in _DEFAULT_ORG_CSV_CANDIDATES)
    raise FileNotFoundError(f"No organization CSV found. Tried: {candidates}")


def _load_org_grp_pairs(csv_path: Optional[Path | str] = None) -> set[tuple[str, str]]:
    """
    Load normalized `(org, grp)` abbreviation pairs from CSV.

    Parameters
    ----------
    csv_path : pathlib.Path | str, optional
        Explicit path to CSV. Uses built-in defaults when omitted.

    Returns
    -------
    set[tuple[str, str]]
        Allowed normalized `(org, grp)` pairs.

    Raises
    ------
    FileNotFoundError
        If the CSV path cannot be found.
    ValueError
        If required columns are missing.
    csv.Error
        If CSV parsing fails.
    OSError
        If file IO fails.
    """
    resolved = _resolve_org_csv_path(csv_path)
    pairs: set[tuple[str, str]] = set()

    with resolved.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Organization CSV is missing a header row.")

        required = {"Org Abbreviation", "Sub-org Abbreviation"}
        missing = required.difference(set(reader.fieldnames))
        if missing:
            raise ValueError(
                f"Organization CSV missing required columns: {sorted(missing)}"
            )

        for row in reader:
            org_raw = (row.get("Org Abbreviation") or "").strip()
            grp_raw = (row.get("Sub-org Abbreviation") or "").strip()
            if not org_raw or not grp_raw:
                continue
            org_f = _to_crockford_fixed(org_raw, ORG_LEN)
            grp_f = _to_crockford_fixed(grp_raw, GRP_LEN)
            pairs.add((org_f, grp_f))

    return pairs


def _validate_org_pair(org: str, grp: str, csv_path: Optional[Path | str] = None) -> bool:
    """
    Check whether an `(org, grp)` pair is present in the organization CSV.

    Parameters
    ----------
    org : str
        Organization abbreviation.
    grp : str
        Sub-organization abbreviation.
    csv_path : pathlib.Path | str, optional
        Explicit CSV path. Uses cached default CSV rows when omitted.

    Returns
    -------
    bool
        ``True`` when the normalized pair exists in the allowed table.
    """
    global _ORG_GRP_CACHE

    try:
        if csv_path is None:
            if _ORG_GRP_CACHE is None:
                _ORG_GRP_CACHE = _load_org_grp_pairs()
            pairs = _ORG_GRP_CACHE
        else:
            pairs = _load_org_grp_pairs(csv_path)
    except (OSError, ValueError, csv.Error):
        return False

    org_f = _to_crockford_fixed(org, ORG_LEN)
    grp_f = _to_crockford_fixed(grp, GRP_LEN)
    return (org_f, grp_f) in pairs


def validate_org(org: str, grp: str, csv_path: Optional[Path | str] = None) -> bool:
    """
    Validate a provided `(org, grp)` abbreviation pair.

    Parameters
    ----------
    org : str
        Organization abbreviation.
    grp : str
        Sub-organization abbreviation.
    csv_path : pathlib.Path | str, optional
        Explicit CSV path for validation.

    Returns
    -------
    bool
        ``True`` when the normalized pair is allowed by the organization table.
    """
    return _validate_org_pair(org=org, grp=grp, csv_path=csv_path)


def validate_role(role: str) -> bool:
    """
    Validate a two-character SEA role code.

    Parameters
    ----------
    role : str
        Role token.

    Returns
    -------
    bool
        ``True`` when `role` is in :data:`ALLOWED_ROLES`.
    """
    return role in ALLOWED_ROLES


def validate_id(sea_id: str) -> bool:
    """
    Validate that a SEA ID matches the canonical fixed-width format.

    Parameters
    ----------
    sea_id : str
        Candidate SEA ID string.

    Returns
    -------
    bool
        ``True`` if `sea_id` matches :data:`ID_RE`.
    """
    return bool(ID_RE.match(sea_id))


class IdFields:
    """
    Parsed SEA ID field container.

    Attributes
    ----------
    org : str
        Organization token.
    grp : str
        Sub-organization token.
    instr : str
        Instrument token.
    role : str
        Role token.
    yymmdd : str
        Date token in UTC `YYMMDD` format.
    hhmmss : str
        Time token in UTC `HHMMSS` format.
    rand : str
        Random Crockford suffix.

    Methods
    -------
    as_dict()
        Return fields as a JSON-serializable dictionary.
    """

    def __init__(
        self,
        org: str,
        grp: str,
        instr: str,
        role: str,
        yymmdd: str,
        hhmmss: str,
        rand: str,
    ) -> None:
        """
        Create a parsed-field value object.

        Parameters
        ----------
        org : str
            Organization token.
        grp : str
            Sub-organization token.
        instr : str
            Instrument token.
        role : str
            Role token.
        yymmdd : str
            UTC date token.
        hhmmss : str
            UTC time token.
        rand : str
            Random suffix.
        """
        self.org = org
        self.grp = grp
        self.instr = instr
        self.role = role
        self.yymmdd = yymmdd
        self.hhmmss = hhmmss
        self.rand = rand

    def as_dict(self) -> dict[str, str]:
        """
        Return parsed fields as a dictionary.

        Returns
        -------
        dict[str, str]
            Mapping for all SEA ID fields.
        """
        return {
            "org": self.org,
            "grp": self.grp,
            "instr": self.instr,
            "role": self.role,
            "yymmdd": self.yymmdd,
            "hhmmss": self.hhmmss,
            "rand": self.rand,
        }

    def __repr__(self) -> str:
        """
        Return a concise developer representation.

        Returns
        -------
        str
            Constructor-like string.
        """
        return (
            "IdFields("
            f"org={self.org!r}, "
            f"grp={self.grp!r}, "
            f"instr={self.instr!r}, "
            f"role={self.role!r}, "
            f"yymmdd={self.yymmdd!r}, "
            f"hhmmss={self.hhmmss!r}, "
            f"rand={self.rand!r})"
        )


def split_id(sea_id: str) -> IdFields:
    """
    Parse a canonical SEA ID into fixed fields.

    Parameters
    ----------
    sea_id : str
        Canonical SEA ID.

    Returns
    -------
    IdFields
        Parsed fields.

    Raises
    ------
    ValueError
        If `sea_id` is not valid.
    """
    if not validate_id(sea_id):
        raise ValueError(f"Invalid ID format: {sea_id}")
    org, grp, instr, role, yymmdd, hhmmss, rand = sea_id.split("-")
    return IdFields(
        org=org,
        grp=grp,
        instr=instr,
        role=role,
        yymmdd=yymmdd,
        hhmmss=hhmmss,
        rand=rand,
    )


def generate_sea_id(
    org: str,
    grp: str,
    instr: str,
    role: str,
    when: Optional[_dt.datetime] = None,
    rand_len: int = RAND_LEN,
    validate_org: bool = True,
) -> str:
    """
    Generate a canonical SEA ID.

    Parameters
    ----------
    org : str
        Organization token source.
    grp : str
        Sub-organization token source.
    instr : str
        Instrument token source.
    role : str
        Two-character role code.
    when : datetime.datetime, optional
        Timestamp for date/time fields. Naive datetimes are treated as UTC.
    rand_len : int, default=RAND_LEN
        Random suffix length.
    validate_org : bool, default=True
        When ``True``, verify `(org, grp)` against the organization CSV table.

    Returns
    -------
    str
        SEA ID string:
        ``<ORG>_2-<GRP>_2-<INST>_5-<ROLE>_2-<YYMMDD>_6-<HHMMSS>_6-<RRR>_3``.

    Raises
    ------
    ValueError
        If `role` is invalid, or if `(org, grp)` is not in the allowed table
        while `validate_org` is enabled.
    RuntimeError
        If generation with default random length produces an invalid ID.
    """
    if not validate_role(role):
        raise ValueError(f"Invalid role: {role}. Allowed: {sorted(ALLOWED_ROLES)}")

    if validate_org and not _validate_org_pair(org=org, grp=grp):
        raise ValueError(
            f"Invalid org/grp pair: {org!r}/{grp!r}. "
            "Pair is not present in the organization CSV."
        )

    if when is None:
        when = _dt.datetime.now(tz=_dt.timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=_dt.timezone.utc)

    when_utc = when.astimezone(_dt.timezone.utc)
    yymmdd = when_utc.strftime("%y%m%d")
    hhmmss = when_utc.strftime("%H%M%S")

    org_f = _to_crockford_fixed(org, ORG_LEN)
    grp_f = _to_crockford_fixed(grp, GRP_LEN)
    instr_f = _to_crockford_fixed(instr, INSTR_LEN)
    rand = _rand_crockford(rand_len)

    sea_id = f"{org_f}-{grp_f}-{instr_f}-{role}-{yymmdd}-{hhmmss}-{rand}"
    if rand_len == RAND_LEN and not validate_id(sea_id):
        raise RuntimeError(f"Generated ID failed validation: {sea_id}")
    return sea_id


def get_org_sea_id(sea_id: str) -> str:
    """
    Derive organization base SEA ID from a canonical SEA ID.

    Parameters
    ----------
    sea_id : str
        Canonical SEA ID.

    Returns
    -------
    str
        Organization base ID: ``ORG-GRP-00000-00-000000-000000-000``.

    Raises
    ------
    ValueError
        If `sea_id` is not valid.
    """
    f = split_id(sea_id)
    org = _to_crockford_fixed(f.org, ORG_LEN)
    grp = _to_crockford_fixed(f.grp, GRP_LEN)
    return f"{org}-{grp}-00000-00-000000-000000-000"


def get_org_ids(sea_id: str, root_ns: Optional[uuid.UUID] = None) -> tuple[str, uuid.UUID]:
    """
    Derive organization base ID and organization UUID.

    Parameters
    ----------
    sea_id : str
        Canonical SEA ID.
    root_ns : uuid.UUID, optional
        Root namespace. Defaults to :data:`PYSEA_NAMESPACE`.

    Returns
    -------
    tuple[str, uuid.UUID]
        ``(org_base_id, org_uuid)``.
    """
    if root_ns is None:
        root_ns = PYSEA_NAMESPACE
    org_base = get_org_sea_id(sea_id)
    org_uuid = uuid.uuid5(root_ns, org_base)
    return org_base, org_uuid


def get_org_uuid(sea_id: str, root_ns: Optional[uuid.UUID] = None) -> uuid.UUID:
    """
    Derive organization UUID from a canonical SEA ID.

    Parameters
    ----------
    sea_id : str
        Canonical SEA ID.
    root_ns : uuid.UUID, optional
        Root namespace.

    Returns
    -------
    uuid.UUID
        Organization UUID.
    """
    _, org_uuid = get_org_ids(sea_id, root_ns)
    return org_uuid


def get_instr_sea_id(sea_id: str) -> str:
    """
    Derive instrument base SEA ID from a canonical SEA ID.

    Parameters
    ----------
    sea_id : str
        Canonical SEA ID.

    Returns
    -------
    str
        Instrument base ID: ``ORG-GRP-INSTR-00-000000-000000-000``.
    """
    f = split_id(sea_id)
    org = _to_crockford_fixed(f.org, ORG_LEN)
    grp = _to_crockford_fixed(f.grp, GRP_LEN)
    instr = _to_crockford_fixed(f.instr, INSTR_LEN)
    return f"{org}-{grp}-{instr}-00-000000-000000-000"


def get_instr_ids(sea_id: str, root_ns: Optional[uuid.UUID] = None) -> tuple[str, uuid.UUID]:
    """
    Derive instrument base ID and instrument UUID.

    Parameters
    ----------
    sea_id : str
        Canonical SEA ID.
    root_ns : uuid.UUID, optional
        Root namespace.

    Returns
    -------
    tuple[str, uuid.UUID]
        ``(instr_base_id, instr_uuid)``.
    """
    if root_ns is None:
        root_ns = PYSEA_NAMESPACE
    org_ns = get_org_uuid(sea_id, root_ns=root_ns)
    instr_base = get_instr_sea_id(sea_id)
    instr_uuid = uuid.uuid5(org_ns, instr_base)
    return instr_base, instr_uuid


def get_instr_uuid(sea_id: str, root_ns: Optional[uuid.UUID] = None) -> uuid.UUID:
    """
    Derive instrument UUID from a canonical SEA ID.

    Parameters
    ----------
    sea_id : str
        Canonical SEA ID.
    root_ns : uuid.UUID, optional
        Root namespace.

    Returns
    -------
    uuid.UUID
        Instrument UUID.
    """
    _, instr_uuid = get_instr_ids(sea_id, root_ns)
    return instr_uuid


def get_data_sea_id(
    org: str,
    grp: str,
    instr: str,
    role: str,
    when: Optional[_dt.datetime] = None,
    rand_len: int = RAND_LEN,
    validate_org: bool = True,
) -> str:
    """
    Generate a fully populated data-level SEA ID.

    Parameters
    ----------
    org : str
        Organization token source.
    grp : str
        Sub-organization token source.
    instr : str
        Instrument token source.
    role : str
        Role code.
    when : datetime.datetime, optional
        Timestamp source.
    rand_len : int, default=RAND_LEN
        Random suffix length.
    validate_org : bool, default=True
        When ``True``, verify `(org, grp)` against the organization CSV table.

    Returns
    -------
    str
        Data-level SEA ID.
    """
    return generate_sea_id(
        org=org,
        grp=grp,
        instr=instr,
        role=role,
        when=when,
        rand_len=rand_len,
        validate_org=validate_org,
    )


def get_data_uuid(sea_id: str, root_ns: Optional[uuid.UUID] = None) -> uuid.UUID:
    """
    Derive data UUID from a canonical SEA ID.

    Parameters
    ----------
    sea_id : str
        Canonical SEA ID.
    root_ns : uuid.UUID, optional
        Root namespace.

    Returns
    -------
    uuid.UUID
        Data UUID.
    """
    if root_ns is None:
        root_ns = PYSEA_NAMESPACE
    instr_ns = get_instr_uuid(sea_id, root_ns=root_ns)
    return uuid.uuid5(instr_ns, sea_id)


def get_data_ids(
    org: str,
    grp: str,
    instr: str,
    role: str,
    when: Optional[_dt.datetime] = None,
    rand_len: int = RAND_LEN,
    root_ns: Optional[uuid.UUID] = None,
    validate_org: bool = True,
) -> tuple[str, uuid.UUID]:
    """
    Generate data SEA ID and corresponding UUID.

    Parameters
    ----------
    org : str
        Organization token source.
    grp : str
        Sub-organization token source.
    instr : str
        Instrument token source.
    role : str
        Role code.
    when : datetime.datetime, optional
        Timestamp source.
    rand_len : int, default=RAND_LEN
        Random suffix length.
    root_ns : uuid.UUID, optional
        Root namespace.
    validate_org : bool, default=True
        When ``True``, verify `(org, grp)` against the organization CSV table.

    Returns
    -------
    tuple[str, uuid.UUID]
        ``(data_id, data_uuid)``.
    """
    if root_ns is None:
        root_ns = PYSEA_NAMESPACE
    sea_id = get_data_sea_id(
        org=org,
        grp=grp,
        instr=instr,
        role=role,
        when=when,
        rand_len=rand_len,
        validate_org=validate_org,
    )
    data_uuid = get_data_uuid(sea_id, root_ns=root_ns)
    return sea_id, data_uuid


def classify_seaid_level(sea_id: str) -> Literal["dataitem", "org", "instrument"]:
    """
    Classify SEA ID level as data, organization-base, or instrument-base.

    Parameters
    ----------
    sea_id : str
        Canonical SEA ID.

    Returns
    -------
    Literal["dataitem", "org", "instrument"]
        SEA ID hierarchy level.

    Raises
    ------
    ValueError
        If `sea_id` is not canonical.
    """
    if not validate_id(sea_id):
        raise ValueError(f"Invalid sea_id for classification: {sea_id}")

    fields = split_id(sea_id)
    is_zero_temporal = (
        fields.role == "00"
        and fields.yymmdd == "000000"
        and fields.hhmmss == "000000"
        and fields.rand == "000"
    )
    if is_zero_temporal:
        if fields.instr == "00000":
            return "org"
        return "instrument"
    return "dataitem"


def seaid_to_uuid5(sea_id: str, namespace: Optional[uuid.UUID] = None) -> uuid.UUID:
    """
    Map SEA ID to deterministic UUIDv5 using hierarchy rules.

    Parameters
    ----------
    sea_id : str
        Canonical SEA ID.
    namespace : uuid.UUID, optional
        Root namespace.

    Returns
    -------
    uuid.UUID
        Deterministic hierarchy UUID.
    """
    if namespace is None:
        namespace = PYSEA_NAMESPACE
    level = classify_seaid_level(sea_id)

    if level == "dataitem":
        return get_data_uuid(sea_id, root_ns=namespace)
    if level == "org":
        return get_org_uuid(sea_id, root_ns=namespace)
    return get_instr_uuid(sea_id, root_ns=namespace)


def sea_to_uuid5(sea_id: str, namespace: Optional[uuid.UUID] = None) -> uuid.UUID:
    """
    Backward-compatible alias for :func:`seaid_to_uuid5`.

    Parameters
    ----------
    sea_id : str
        Canonical SEA ID.
    namespace : uuid.UUID, optional
        Root namespace.

    Returns
    -------
    uuid.UUID
        Deterministic hierarchy UUID.
    """
    return seaid_to_uuid5(sea_id=sea_id, namespace=namespace)


class SEAID:
    """
    SEA ID object with parsed fields and derived hierarchy IDs/UUIDs.

    Attributes
    ----------
    org : str
        Organization token.
    grp : str
        Sub-organization token.
    instr : str
        Instrument token.
    role : str
        Role token.
    yymmdd : str
        Date token.
    hhmmss : str
        Time token.
    rand : str
        Random suffix.
    seaid : str
        Canonical SEA ID.
    uuid : uuid.UUID
        Deterministic UUID mapped from `seaid`.
    namespace : uuid.UUID
        Root UUID namespace used for derivation.
    org_seaid : str
        Organization base ID.
    org_uuid : uuid.UUID
        Organization UUID.
    instr_seaid : str | None
        Instrument base ID when applicable.
    instr_uuid : uuid.UUID | None
        Instrument UUID when applicable.
    seaid_type : Literal["dataitem", "instrument", "org"]
        Hierarchy level classification.
    is_org_base_instance : bool
        Whether this ID is organization-base.
    is_instr_base_instance : bool
        Whether this ID is instrument-base.

    Methods
    -------
    print_ids()
        Print data/instrument/organization IDs and UUIDs.
    to_dict()
        Export object fields and derived values as dictionary.
    """

    def __init__(
        self,
        org: Optional[str] = None,
        grp: Optional[str] = None,
        instr: Optional[str] = None,
        role: Optional[str] = None,
        when: Optional[_dt.datetime] = None,
        rand_len: int = RAND_LEN,
        seaid: Optional[str] = None,
        namespace: Optional[uuid.UUID] = None,
        validate_org: bool = True,
    ) -> None:
        """
        Initialize from existing SEA ID or from component fields.

        Parameters
        ----------
        org : str, optional
            Organization token source.
        grp : str, optional
            Sub-organization token source.
        instr : str, optional
            Instrument token source.
        role : str, optional
            Role token source.
        when : datetime.datetime, optional
            Timestamp used when generating `seaid`.
        rand_len : int, default=RAND_LEN
            Random suffix length used for generation.
        seaid : str, optional
            Existing canonical SEA ID to parse.
        namespace : uuid.UUID, optional
            Root namespace for UUID derivation.
        validate_org : bool, default=True
            When ``True``, verify `(org, grp)` against the organization CSV table.

        Raises
        ------
        ValueError
            If `seaid` is invalid, or if field-based creation omits required fields.
        """
        self.namespace = namespace if namespace is not None else PYSEA_NAMESPACE

        if seaid is not None:
            if not validate_id(seaid):
                raise ValueError(f"Invalid seaid: {seaid}")
            resolved_seaid = seaid
        else:
            if None in (org, grp, instr, role):
                raise ValueError("org, grp, instr, and role are required when seaid is not provided.")
            resolved_seaid = generate_sea_id(
                org=org,
                grp=grp,
                instr=instr,
                role=role,
                when=when,
                rand_len=rand_len,
                validate_org=validate_org,
            )

        fields = split_id(resolved_seaid)
        self.org = fields.org
        self.grp = fields.grp
        self.instr = fields.instr
        self.role = fields.role
        self.yymmdd = fields.yymmdd
        self.hhmmss = fields.hhmmss
        self.date = self.yymmdd
        self.time = self.hhmmss
        self.rand = fields.rand

        self.seaid = resolved_seaid
        self.uuid = seaid_to_uuid5(self.seaid, namespace=self.namespace)

        self.seaid_type = classify_seaid_level(self.seaid)
        self.is_org_base_instance = self.seaid_type == "org"
        self.is_instr_base_instance = self.seaid_type == "instrument"

        if self.seaid_type == "dataitem":
            self.org_seaid, self.org_uuid = get_org_ids(self.seaid, root_ns=self.namespace)
            self.instr_seaid, self.instr_uuid = get_instr_ids(self.seaid, root_ns=self.namespace)
        elif self.seaid_type == "instrument":
            self.org_seaid, self.org_uuid = get_org_ids(self.seaid, root_ns=self.namespace)
            self.instr_seaid, self.instr_uuid = self.seaid, self.uuid
        elif self.seaid_type == "org":
            self.org_seaid, self.org_uuid = self.seaid, self.uuid
            self.instr_seaid, self.instr_uuid = None, None
        else:
            raise ValueError(f"Unexpected seaid_type: {self.seaid_type}")

    def print_ids(self) -> None:
        """
        Print ID and UUID hierarchy to standard output.

        Returns
        -------
        None
            This method has side effects only.
        """
        print("Dataitem IDs:")
        print(f"   seaid: {self.seaid}")
        print(f"    uuid: {self.uuid}")
        print("Instrument IDs:")
        print(f"   seaid: {self.instr_seaid}")
        print(f"    uuid: {self.instr_uuid}")
        print("Organization IDs:")
        print(f"   seaid: {self.org_seaid}")
        print(f"    uuid: {self.org_uuid}")

    def to_dict(self) -> dict[str, str | bool]:
        """
        Return JSON-serializable object data.

        Returns
        -------
        dict[str, str | bool]
            Parsed fields and derived identifiers.
        """
        return {
            "org": self.org,
            "grp": self.grp,
            "instr": self.instr,
            "role": self.role,
            "date": self.date,
            "time": self.time,
            "rand": self.rand,
            "seaid": self.seaid,
            "uuid": str(self.uuid),
            "namespace": str(self.namespace),
            "org_seaid": self.org_seaid,
            "org_uuid": str(self.org_uuid),
            "instr_seaid": self.instr_seaid,
            "instr_uuid": str(self.instr_uuid),
            "is_org_base_instance": self.is_org_base_instance,
            "is_instr_base_instance": self.is_instr_base_instance,
        }

    def __repr__(self) -> str:
        """
        Return concise developer representation.

        Returns
        -------
        str
            Canonical SEA ID.
        """
        return self.seaid


def main() -> None:
    """
    Command-line entry point for SEA ID generation and parsing.

    Returns
    -------
    None
        This function prints values to standard output.
    """
    p = argparse.ArgumentParser(description="Generate pySEA sea_ids (Crockford Base32-safe) + UUIDv5.")
    p.add_argument("--org", required=True, help="Organization code (will be normalized to 2 chars)")
    p.add_argument("--grp", required=True, help="Sub-organization code (will be normalized to 2 chars)")
    p.add_argument("--instr", required=True, help="Instrument code (will be normalized to 5 chars)")
    p.add_argument("--role", required=True, help="Role code (e.g. E0, TE, TS, 00)")
    p.add_argument("--no-validate-org", action="store_true", help="Skip org/grp CSV validation.")
    p.add_argument("--utc", action="store_true", help="Use current UTC time (default).")
    p.add_argument("--time", default=None, help="Optional time as ISO8601 (e.g. 2026-02-10T12:34:00Z)")
    args = p.parse_args()

    when: _dt.datetime | None = None
    if args.time:
        s = args.time.strip().replace("Z", "+00:00")
        when = _dt.datetime.fromisoformat(s)

    hid = generate_sea_id(
        args.org,
        args.grp,
        args.instr,
        args.role,
        when=when,
        validate_org=not args.no_validate_org,
    )
    u5 = seaid_to_uuid5(hid)
    fields = split_id(hid)

    print(hid)
    print(f"uuid5: {u5}")
    print(f"parsed: {fields}")


if __name__ == "__main__":
    main()
