# from __future__ import annotations
# from typing import Any, Dict

# from stages.prompt import enhance_prompt
# from stages.prompt_firewall import sanitize_prompt
# from stages.llm import stream_code
# from stages.semgrep_registry import run_semgrep_registry_over_blob
# from stages.uml_pipeline import run_uml_pipeline_over_blob


# async def run_pipeline(prompt: str) -> Dict[str, Any]:
#     """
#     Main pipeline: sanitize -> enhance -> generate -> SAST -> UML diagram
#     Return code + security report (Semgrep + UML) to the API layer
#     """

#     # 1) Prompt hygiene (firewall + enhancement)
#     safe_prompt = sanitize_prompt(prompt or "")
#     enhanced = enhance_prompt(safe_prompt)
#     hardened_prompt: str = enhanced["text"]
#     policy_version: str = enhanced.get("policy_version", "v1")

#     # 2) LLM code generation (stream into a single string)
#     parts: list[str] = []
#     async for chunk in stream_code(hardened_prompt):
#         if not chunk:
#             continue
#         parts.append(chunk)

#     code_blob = "".join(parts).strip()
#     if not code_blob:
#         code_blob = "// empty"

#     # 3) Static analysis (Semgrep) over the generated code
#     semgrep_report = run_semgrep_registry_over_blob(code_blob)

#     # 4) UML pipeline (CIR -> PlantUML -> SVG) over the same blob
#     uml_report = run_uml_pipeline_over_blob(code_blob)

#     # 5) Final result consumed by FastAPI endpoint (/api/generate)
#     return {
#         "code": code_blob,
#         "report": {
#             "policy_version": policy_version,
#             "prompt_after_enhancement": hardened_prompt,
#             "semgrep": semgrep_report,
#             "uml": uml_report,
#         },
#         "decision": "CODE_ONLY",
#     }

# backend/vibe-secure-gen/pipeline.py

"""
Enhanced pipeline with hybrid autofix:
1. Generate code with LLM
2. Semgrep scan + native autofix (~35% of issues)
3. LLM-based fix for remaining complex issues (~65%)
4. Final verification
5. UML generation
"""

from typing import Dict, Any

from stages.prompt import enhance_prompt
from stages.prompt_firewall import sanitize_prompt
from stages.llm import stream_code
from stages.semgrep_smart_fix import run_semgrep_smart_fix
from stages.llm_fix import fix_with_llm
from stages.uml_pipeline import run_uml_pipeline_over_blob


async def run_pipeline(prompt: str) -> Dict[str, Any]:
    """
    Main pipeline with intelligent hybrid autofix.
    
    Pipeline stages:
    1. Prompt sanitization & enhancement
    2. LLM code generation
    3. Semgrep analysis with native autofix
    4. LLM-based fixing for remaining issues
    5. Final verification scan
    6. UML diagram generation
    
    Returns complete report with fixed code.
    """
    
    print("=" * 80)
    print("🔒 SECURE CODE GENERATION PIPELINE")
    print("=" * 80)
    
    # ===== STAGE 1: PROMPT PROCESSING =====
    print("\n📝 Stage 1: Processing prompt...")
    safe_prompt = sanitize_prompt(prompt or "")
    enhanced = enhance_prompt(safe_prompt)
    hardened_prompt: str = enhanced["text"]
    policy_version: str = enhanced.get("policy_version", "v1")
    
    # ===== STAGE 2: CODE GENERATION =====
    print("\n🤖 Stage 2: Generating code with LLM...")
    parts = []
    async for chunk in stream_code(hardened_prompt):
        if chunk:
            parts.append(chunk)
    
    original_code = "".join(parts).strip()
    if not original_code:
        original_code = "// empty"
    
    print(f"   Generated {len(original_code)} characters")
    
    # ===== STAGE 3: SEMGREP ANALYSIS + AUTOFIX =====
    print("\n🔍 Stage 3: Security analysis (Semgrep)...")
    semgrep_result = run_semgrep_smart_fix(original_code)
    
    if not semgrep_result.get("ok"):
        # Semgrep failed - return original code with error
        print(f"   Semgrep failed: {semgrep_result.get('error')}")
        return {
            "code": original_code,
            "original_code": original_code,
            "report": {
                "policy_version": policy_version,
                "semgrep_error": semgrep_result.get("error"),
                "uml": {"ok": False, "error": "Skipped due to Semgrep failure"}
            },
            "decision": "CODE_ONLY",
        }
    
    current_code = semgrep_result.get("code", original_code)
    semgrep_fixed = semgrep_result.get("fixes_applied", 0)
    
    # ===== STAGE 4: LLM-BASED FIXING (IF NEEDED) =====
    llm_fix_result = None
    remaining_issues = semgrep_result.get("categorized_findings", {}).get("remaining_needs_llm", [])
    
    # Only use LLM if:
    # 1. There are remaining issues
    # 2. Not too many issues (avoid overwhelming LLM)
    # 3. Focus on HIGH/CRITICAL severity
    if remaining_issues:
        # Filter for critical issues
        critical_issues = [
            f for f in remaining_issues 
            if f.get('severity', '').upper() in ['CRITICAL', 'HIGH', 'ERROR']
        ]
        
        # Decide what to fix with LLM
        issues_to_fix = critical_issues if critical_issues else remaining_issues[:10]
        
        if len(issues_to_fix) > 0 and len(issues_to_fix) <= 10:
            print(f"\n🤖 Stage 4: LLM fixing {len(issues_to_fix)} complex issues...")
            llm_fix_result = await fix_with_llm(current_code, issues_to_fix)
            
            if llm_fix_result.get("fixed"):
                current_code = llm_fix_result["code"]
                print(f"   LLM fixed {llm_fix_result['fixes_applied']} additional issues")
            else:
                print(f"   LLM fix unsuccessful: {llm_fix_result.get('error', 'Unknown')}")
        
        elif len(issues_to_fix) > 10:
            print(f"\n⚠️  Stage 4: {len(remaining_issues)} issues remain (too many for LLM autofix)")
            print(f"   Recommend manual review for remaining issues")
            llm_fix_result = {
                "fixed": False,
                "attempted": False,
                "reason": f"Too many issues ({len(remaining_issues)}) - manual review recommended"
            }
    else:
        print(f"\n📝 Stage 4: No remaining issues - LLM fix not needed")
    
    # ===== STAGE 5: UML GENERATION =====
    print("\n📊 Stage 5: Generating UML diagrams...")
    uml_report = run_uml_pipeline_over_blob(current_code)
    
    # ===== FINAL SUMMARY =====
    total_fixes = semgrep_fixed
    if llm_fix_result and llm_fix_result.get("fixed"):
        total_fixes += llm_fix_result.get("fixes_applied", 0)
    
    initial_issues = semgrep_result.get("findings_before", 0)
    final_issues = semgrep_result.get("findings_after", 0)
    if llm_fix_result and llm_fix_result.get("fixed"):
        final_issues = llm_fix_result.get("issues_after", final_issues)
    
    print("\n" + "=" * 80)
    print(" PIPELINE COMPLETE")
    print("=" * 80)
    print(f"📈 Results:")
    print(f"   • Initial vulnerabilities: {initial_issues}")
    print(f"   • Semgrep auto-fixed: {semgrep_fixed}")
    if llm_fix_result and llm_fix_result.get("fixed"):
        print(f"   • LLM fixed: {llm_fix_result.get('fixes_applied', 0)}")
    print(f"   • Total fixed: {total_fixes}")
    print(f"   • Remaining issues: {final_issues}")
    if total_fixes > 0:
        fix_rate = (total_fixes / initial_issues * 100) if initial_issues > 0 else 0
        print(f"   • Fix rate: {fix_rate:.1f}%")
    print("=" * 80 + "\n")
    
    # ===== RETURN RESULTS =====
    return {
        "code": current_code,
        "original_code": original_code,
        "report": {
            "policy_version": policy_version,
            "prompt_after_enhancement": hardened_prompt,
            "semgrep": {
                "ok": semgrep_result.get("ok", False),
                "initial_findings": initial_issues,
                "final_findings": final_issues,
                "autofix_applied": semgrep_result.get("autofix_applied", False),
                "fixes_applied": semgrep_fixed,
                "auto_fixable_count": semgrep_result.get("auto_fixable_count", 0),
                "manual_only_count": semgrep_result.get("manual_only_count", 0),
                "packs": semgrep_result.get("packs", []),
                "languages": semgrep_result.get("languages", []),
                "file_count": semgrep_result.get("file_count", 0),
                "categorized_findings": semgrep_result.get("categorized_findings", {}),
            },
            "llm_fix": llm_fix_result,
            "uml": uml_report,
            "total_fixes_applied": total_fixes,
            "fix_summary": {
                "initial_issues": initial_issues,
                "semgrep_fixed": semgrep_fixed,
                "llm_fixed": llm_fix_result.get("fixes_applied", 0) if llm_fix_result and llm_fix_result.get("fixed") else 0,
                "remaining_issues": final_issues,
                "fix_rate_percent": round((total_fixes / initial_issues * 100) if initial_issues > 0 else 100, 1)
            }
        },
        "decision": "CODE_FIXED" if total_fixes > 0 else "CODE_ONLY",
    }