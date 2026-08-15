"""
translation_layer.py — Module E: multilingual alert dispatch.

DESIGN DECISION (worth stating explicitly in the pitch): Tier 1/2/3
alerts are drawn from a small, FIXED set of safety-critical templates
(e.g. "move to nearest exit," "do not push"), not free-form text. For
exactly this reason, this module uses a CURATED PHRASEBOOK as the
primary translation path for those fixed templates, rather than routing
life-safety instructions through a generic machine-translation API.

This is a deliberate safety choice, not a shortcut: a generic MT API
can mistranslate urgent safety instructions in ways that are hard to
catch automatically, and safety-critical crowd instructions are exactly
the wrong place to accept that risk. A curated, human-reviewable
phrasebook is the more defensible design for this specific use case.

HONESTY NOTE ON TRANSLATION ACCURACY (do not skip this in the pitch):
Phrasebook entries below are a first-pass implementation, NOT verified
by a native speaker or professional translator. Every non-English entry
is flagged accordingly. Before any real deployment, every phrase MUST
be reviewed by a native speaker / professional translation service --
this is a hackathon-stage placeholder for the phrasebook CONTENT, even
though the phrasebook ARCHITECTURE itself (lookup, fallback, per-tier
templates) is fully real and functional.

For free-form/non-template text (e.g. GenAI incident summaries, which
aren't safety-critical dispatch instructions), a generic translation
API fallback is provided, following the same honest mock-when-no-key
pattern used in Module C's weather client.
"""

import os
from dataclasses import dataclass

import requests

GOOGLE_TRANSLATE_URL = "https://translation.googleapis.com/language/translate/v2"

SUPPORTED_LANGUAGES = ["en", "hi", "ta"]  # English, Hindi, Tamil -- Tamil Nadu is CrowdShield's primary case-study region

# Curated safety phrasebook. NEEDS_NATIVE_REVIEW=True flags every entry
# that has not been verified by a native speaker -- currently ALL non-
# English entries, stated honestly rather than silently shipped as if
# verified.
_PHRASEBOOK: dict[str, dict[str, dict]] = {
    "tier1_reroute": {
        "en": {"text": "Please move calmly toward the marked alternate route.", "needs_native_review": False},
        "hi": {"text": "कृपया शांति से चिह्नित वैकल्पिक मार्ग की ओर बढ़ें।", "needs_native_review": True},
        "ta": {"text": "தயவுசெய்து குறிக்கப்பட்ட மாற்று வழியை நோக்கி அமைதியாக நகரவும்.", "needs_native_review": True},
    },
    "tier2_dispersal": {
        "en": {"text": "For your safety, please move slowly away from this area. Do not push.", "needs_native_review": False},
        "hi": {"text": "आपकी सुरक्षा के लिए, कृपया धीरे-धीरे इस क्षेत्र से दूर हटें। धक्का न दें।", "needs_native_review": True},
        "ta": {"text": "உங்கள் பாதுகாப்பிற்காக, இந்த பகுதியிலிருந்து மெதுவாக விலகிச் செல்லவும். தள்ளாதீர்கள்.", "needs_native_review": True},
    },
    "tier3_evacuate": {
        "en": {"text": "Emergency: please evacuate this area now via the nearest marked exit.", "needs_native_review": False},
        "hi": {"text": "आपातकाल: कृपया निकटतम चिह्नित निकास से अभी इस क्षेत्र को खाली करें।", "needs_native_review": True},
        "ta": {"text": "அவசரநிலை: அருகிலுள்ள குறிக்கப்பட்ட வெளியேறும் வழி வழியாக இப்போது இந்த பகுதியை காலி செய்யவும்.", "needs_native_review": True},
    },
}


@dataclass
class TranslatedAlert:
    template_key: str
    translations: dict[str, str]     # lang_code -> text
    languages_needing_review: list[str]


def get_multilingual_alert(template_key: str,
                            languages: list[str] = SUPPORTED_LANGUAGES) -> TranslatedAlert:
    """Primary path for Tier 1/2/3 dispatch alerts -- fixed templates,
    curated phrasebook, no live API dependency (works even if the
    network is degraded, which matters for an emergency alert)."""
    if template_key not in _PHRASEBOOK:
        raise ValueError(f"Unknown alert template '{template_key}'. "
                          f"Available: {list(_PHRASEBOOK.keys())}")

    entry = _PHRASEBOOK[template_key]
    translations = {}
    needs_review = []
    for lang in languages:
        if lang not in entry:
            continue
        translations[lang] = entry[lang]["text"]
        if entry[lang]["needs_native_review"]:
            needs_review.append(lang)

    return TranslatedAlert(
        template_key=template_key,
        translations=translations,
        languages_needing_review=needs_review,
    )


def translate_freeform_text(text: str, target_language: str, api_key: str | None = None) -> dict:
    """
    Fallback path for NON-safety-critical free text (e.g. GenAI incident
    summaries for a report, not a live dispatch instruction). Uses
    Google Cloud Translate if an API key is configured; otherwise
    returns a clearly-labeled untranslated passthrough -- same honest
    pattern as Module C's weather client.
    """
    api_key = api_key or os.environ.get("GOOGLE_TRANSLATE_API_KEY")

    if not api_key:
        return {
            "translated_text": text,
            "target_language": target_language,
            "is_mock": True,
            "note": "No GOOGLE_TRANSLATE_API_KEY configured -- returning original "
                    "text untranslated. Set the environment variable to enable live translation.",
        }

    try:
        resp = requests.post(
            GOOGLE_TRANSLATE_URL,
            params={"key": api_key},
            json={"q": text, "target": target_language, "format": "text"},
            timeout=8,
        )
        resp.raise_for_status()
        translated = resp.json()["data"]["translations"][0]["translatedText"]
        return {
            "translated_text": translated,
            "target_language": target_language,
            "is_mock": False,
            "note": "Live Google Cloud Translate result.",
        }
    except Exception as e:
        return {
            "translated_text": text,
            "target_language": target_language,
            "is_mock": True,
            "note": f"Live translation API call failed ({type(e).__name__}: {e}) -- "
                    f"returning original text untranslated.",
        }
