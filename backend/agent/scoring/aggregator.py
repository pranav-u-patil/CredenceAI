from scoring.gemini_final import gemini_final_judge


dossier = {
    "summary": aggregation,
    "top_evidence": sorted(
        all_units,
        key=lambda x: abs(float(x.get("similarity", 0))),
        reverse=True
    )[:10]
}

gemini_result = await gemini_final_judge(
    claim_input.claim_text,
    dossier,
    settings.gemini_api_key
)

output = {
    "claim_id": claim_input.claim_id,
    "result": gemini_result,
    "evidence_units": all_units,
    "meta": {
        "searches": _count_searches(pipeline_results),
        "retries": retries
    }
}