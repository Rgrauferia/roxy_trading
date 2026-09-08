"""Reviewed source metadata for Home fitness; not clinical rules or a catalogue.

No provider is activated by this registry. Public source links do not grant Roxy
permission to reproduce a screening instrument or prescribe an exercise plan.
There are deliberately no exercise IDs, questionnaires, videos, or user data.
"""

from copy import deepcopy


CHECKED_ON = "2026-09-08"
REGISTRY_VERSION = "fitness-sources-20260908-v1"

_SOURCES = (
    {
        "id": "cdc-adult-activity",
        "publisher": "CDC",
        "title": "Actividad física para adultos",
        "url": "https://www.cdc.gov/physical-activity-basics/guidelines/adults.html",
        "kind": "general_education",
        "language": "en",
        "source_version": "2023-12-20",
        "status": "external_link_available",
        "summary": "Guía general para comprender actividad aeróbica y fortalecimiento. No es un plan individual.",
        "content_imported": False,
        "clinical_approval": False,
    },
    {
        "id": "csep-get-active",
        "publisher": "CSEP",
        "title": "Antes de comenzar: orientación de CSEP",
        "url": "https://csep.ca/2021/01/20/pre-screening-for-physical-activity/",
        "kind": "general_education",
        "language": "en",
        "source_version": "linked_questionnaire_copyright_2017",
        "status": "external_link_only_software_license_pending",
        "summary": "Recurso externo sobre preparación para la actividad física. Roxy no administra ni interpreta este cuestionario.",
        "permission_source_id": "csep-permissions",
        "published_document_languages": ["en", "fr"],
        "content_imported": False,
        "clinical_approval": False,
    },
    {
        "id": "csep-permissions",
        "publisher": "CSEP",
        "title": "Permisos de uso del cuestionario",
        "url": "https://csep.ca/contact-us/permissions/",
        "kind": "license_policy",
        "language": "en",
        "source_version": "2025-12-10",
        "status": "software_license_and_professional_review_required",
        "software_reproduction_approved": False,
        "translation_approved": False,
        "clinical_approval": False,
    },
    {
        "id": "wger-license",
        "publisher": "wger project",
        "title": "wger: licencias de software y contenido",
        "url": "https://wger.readthedocs.io/en/latest/",
        "kind": "license_policy",
        "language": "en",
        "source_version": "documentation_2.7_observed",
        "status": "resource_by_resource_review_required",
        "software_license": "AGPL-3.0-or-later",
        "initial_data_license": "CC-BY-SA-3.0",
        "blanket_media_license": False,
        "catalogue_imported": False,
        "clinical_approval": False,
    },
    {
        "id": "wger-api",
        "publisher": "wger project",
        "title": "wger: documentación de API",
        "url": "https://wger.readthedocs.io/en/latest/api/api.html",
        "kind": "provider_documentation",
        "language": "en",
        "source_version": "documentation_2.7_observed",
        "status": "anonymous_read_probe_only_not_integrated",
        "public_catalogue_requires_account": False,
        "user_owned_data_requires_authentication": True,
        "read_probe": {
            "checked_on": CHECKED_ON,
            "http_status": 200,
            "scope": "one_exercise_metadata_and_license_list_only",
            "license_list_url": "https://wger.de/api/v2/license/?limit=20",
            "sample_url": "https://wger.de/api/v2/exerciseinfo/?limit=1",
            "sample_media_complete": False,
        },
        "production_enabled": False,
        "clinical_approval": False,
    },
    {
        "id": "musclewiki-plans",
        "publisher": "MuscleWiki",
        "title": "MuscleWiki: planes de API",
        "url": "https://api.musclewiki.com/",
        "kind": "provider_pricing",
        "language": "en",
        "source_version": "live_page_checked_2026-09-08",
        "status": "candidate_not_contracted",
        "currency": "USD",
        "price_frequency": "month",
        "published_plans": [
            {"name": "BASIC", "price": 0, "calls": 500, "application_access": False},
            {"name": "TESTING", "price": 10, "calls": 1000, "languages": ["en"], "routines": False},
            {"name": "GROWTH", "price": 39.99, "calls": 30000, "spanish": True, "routines": False},
        ],
        "price_is_quote": False,
        "production_enabled": False,
        "clinical_approval": False,
    },
    {
        "id": "musclewiki-terms",
        "publisher": "MuscleWiki",
        "title": "MuscleWiki: condiciones de datos y medios",
        "url": "https://api.musclewiki.com/api-terms",
        "kind": "license_policy",
        "language": "en",
        "source_version": "2026-08-12",
        "status": "subscription_and_terms_acceptance_pending",
        "metadata_max_cache_days": 30,
        "permanent_media_storage_allowed": False,
        "video_rehosting_allowed": False,
        "keep_embedded_branding": True,
        "legal_credit": "Exercise data and videos provided by MuscleWiki.com",
        "model_training_permission_obtained": False,
        "clinical_approval": False,
    },
    {
        "id": "musclewiki-faq",
        "publisher": "MuscleWiki",
        "title": "MuscleWiki: funcionamiento y límites",
        "url": "https://api.musclewiki.com/faq",
        "kind": "provider_documentation",
        "language": "en",
        "source_version": "live_page_checked_2026-09-08",
        "status": "candidate_not_integrated",
        "stream_ranges_consume_quota": True,
        "video_cache_policy": "transient_playback_only",
        "thumbnail_cache_policy": "private_client_only_up_to_24_hours",
        "bodymap_cache_policy": "honor_no_store_response_header",
        "permanent_key_in_client": False,
        "notes": "Aplicar la política más restrictiva de caché y los headers; no asumir cobertura de medios por el nombre del plan.",
        "clinical_approval": False,
    },
)


def fitness_sources() -> dict:
    """Return a detached source registry, without fetching or activating content."""
    return {
        "version": REGISTRY_VERSION,
        "checked_on": CHECKED_ON,
        "status": "research_only_no_clinical_or_partner_approval",
        "sources": deepcopy(list(_SOURCES)),
    }


def fitness_education_links() -> list[dict]:
    """External educational pages; no questionnaire, prescription or media embed."""
    return [
        {
            "id": source["id"],
            "title": source["title"],
            "publisher": source["publisher"],
            "url": source["url"],
            "language": source["language"],
            "summary": source["summary"],
            "checked_on": CHECKED_ON,
            "external": True,
            "clinical_approval": False,
        }
        for source in _SOURCES
        if source["kind"] == "general_education"
    ]
