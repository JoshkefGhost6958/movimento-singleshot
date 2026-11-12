"""
Seed dummy data for the Kinetic Ledger development environment.

Populates:
  - SDTVET (governance body)
  - TVETInstitution (2 registered institutions)
  - InstitutionAPIKey (one key per institution)
  - MotionCatalogue + MotionDefinition + MotionSemantics + CaptureContract

Usage:
    python scripts/seed_dummy_data.py
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

from kinetic_ledger.database.database import SessionLocal, init_db
from kinetic_ledger.models.sdtvet import SDTVET
from kinetic_ledger.models.institutions import TVETInstitution, InstitutionAPIKey
from kinetic_ledger.models.motion_catalogue import (
    MotionCatalogue,
    MotionDefinition,
    MotionSemantics,
    CaptureContract,
)


def _hashed_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        # SDTVET
        sdtvet = db.query(SDTVET).filter_by(name="SDTVET Governing Body").first()
        if not sdtvet:
            sdtvet = SDTVET(name="SDTVET Governing Body", status="ACTIVE")
            db.add(sdtvet)
            db.flush()
            print(f"[+] Created SDTVET: {sdtvet.id}")
        else:
            print(f"[~] SDTVET already exists: {sdtvet.id}")

        # Institutions
        institutions_data = [
            {"code": "TVET-NBI-001", "name": "Nairobi Institute of Motion Sciences"},
            {"code": "TVET-MSA-002", "name": "Mombasa Kinetics & Animation Academy"},
        ]
        created_institutions = []
        for data in institutions_data:
            inst = db.query(TVETInstitution).filter_by(institution_code=data["code"]).first()
            if not inst:
                inst = TVETInstitution(
                    institution_code=data["code"],
                    name=data["name"],
                    status="ACTIVE",
                    sdtvet_id=sdtvet.id,
                )
                db.add(inst)
                db.flush()
                print(f"[+] Created Institution: {inst.name} ({inst.institution_id})")
            else:
                print(f"[~] Institution already exists: {inst.name}")
            created_institutions.append(inst)

        # API Keys
        api_key_raws = {
            "TVET-NBI-001": "dev-api-key-nairobi-institute-001",
            "TVET-MSA-002": "dev-api-key-mombasa-kinetics-002",
        }
        for inst in created_institutions:
            raw_key = api_key_raws[inst.institution_code]
            hashed = _hashed_key(raw_key)
            existing = db.query(InstitutionAPIKey).filter_by(key_hash=hashed).first()
            if not existing:
                api_key = InstitutionAPIKey(
                    institution_id=inst.institution_id,
                    key_hash=hashed,
                    name=f"Dev key for {inst.name}",
                    status="ACTIVE",
                )
                db.add(api_key)
                db.flush()
                print(f"[+] API Key for {inst.name}  ->  raw: {raw_key}")
            else:
                print(f"[~] API Key already exists for {inst.name}")

        # Motion Catalogue
        catalogue = db.query(MotionCatalogue).filter_by(version="v1.0.0").first()
        if not catalogue:
            catalogue = MotionCatalogue(version="v1.0.0", status="PUBLISHED")
            db.add(catalogue)
            db.flush()
            print(f"[+] Created MotionCatalogue v1.0.0 ({catalogue.catalogue_id})")
        else:
            print(f"[~] MotionCatalogue v1.0.0 already exists")

        # Motion Definitions
        definitions_data = [
            {
                "code": "WALK-NEUTRAL-001", "name": "Neutral Walk Cycle",
                "description": "Standard human bipedal walk at natural pace.",
                "category": "locomotion", "version": "1.0",
                "intent": "Capture a relaxed, forward-facing human walking motion at ~1.4 m/s.",
                "attrs": {"style": "neutral", "speed_ms": 1.4, "direction": "forward"},
                "formats": ["FBX", "BVH"], "fps": 60, "min_dur": 2, "max_dur": 10,
            },
            {
                "code": "RUN-SPRINT-001", "name": "Sprint Run Cycle",
                "description": "High-speed bipedal sprint.",
                "category": "locomotion", "version": "1.0",
                "intent": "Capture a full-body sprint cycle at maximum effort (~7 m/s).",
                "attrs": {"style": "sprint", "speed_ms": 7.0, "direction": "forward"},
                "formats": ["FBX"], "fps": 120, "min_dur": 1, "max_dur": 5,
            },
            {
                "code": "FIGHT-HOOK-001", "name": "Left Hook Punch",
                "description": "Combat left hook strike sequence.",
                "category": "combat", "version": "1.0",
                "intent": "Capture a standing left hook punch from guard stance.",
                "attrs": {"style": "combat", "dominant_limb": "left", "stance": "guard"},
                "formats": ["FBX", "BVH"], "fps": 60, "min_dur": 1, "max_dur": 3,
            },
        ]
        for d in definitions_data:
            existing_def = db.query(MotionDefinition).filter_by(motion_code=d["code"]).first()
            if not existing_def:
                defn = MotionDefinition(
                    catalogue_id=catalogue.catalogue_id,
                    motion_code=d["code"], name=d["name"],
                    description=d["description"], category=d["category"],
                    version=d["version"], status="ACTIVE",
                )
                db.add(defn)
                db.flush()
                db.add(MotionSemantics(
                    motion_definition_id=defn.motion_definition_id,
                    intent=d["intent"], semantic_attributes=d["attrs"],
                ))
                db.add(CaptureContract(
                    motion_definition_id=defn.motion_definition_id,
                    accepted_file_formats=d["formats"], fps_requirements=d["fps"],
                    min_duration_sec=d["min_dur"], max_duration_sec=d["max_dur"],
                    capture_quality_requirements={"min_joint_count": 24},
                ))
                db.flush()
                print(f"[+] Created MotionDefinition: {d['name']} ({d['code']})")
            else:
                print(f"[~] MotionDefinition already exists: {d['code']}")

        db.commit()
        print("\n[OK] Seed complete.")

    except Exception as exc:
        db.rollback()
        print(f"\n[FAIL] Seed failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
