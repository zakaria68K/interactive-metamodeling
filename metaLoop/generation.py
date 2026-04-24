from typing import Callable
from .state import State
import re


def _chunk_class_names(chunk: str) -> list[str]:
    return re.findall(r"create\s+(?:abstract\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)", chunk, re.IGNORECASE)


def _filter_chunk_for_isolated_display(chunk: str, allowed_classes: list[str]) -> str:
    """Remove references/containments that point to classes outside the allowed set, 
    and remove entire class definitions for classes not in the allowed set."""
    lines = chunk.split("\n")
    filtered_lines = []
    
    # Regex to match reference/containment lines
    ref_pattern = re.compile(
        r"^\s*create\s+(?:reference|containment)\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+([A-Za-z_][A-Za-z0-9_]*)\s+type\s+([A-Za-z_][A-Za-z0-9_]*)",
        re.IGNORECASE
    )
    # Regex to match class definition blocks
    class_pattern = re.compile(r"^\s*create\s+(?:abstract\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
    attr_pattern = re.compile(r"^\s*create\s+(?:attribute|reference|containment)\s+.+\s+in\s+([A-Za-z_][A-Za-z0-9_]*)", re.IGNORECASE)
    
    current_class = None
    skip_block = False
    
    for line in lines:
        # Check if this starts a new class definition
        class_match = class_pattern.match(line)
        if class_match:
            current_class = class_match.group(1)
            skip_block = current_class not in allowed_classes
            if skip_block:
                continue
        
        # Check if this line belongs to a class (attribute/reference definition)
        attr_match = attr_pattern.match(line)
        if attr_match:
            owner_class = attr_match.group(1)
            if owner_class not in allowed_classes:
                continue  # Skip attributes for external classes
        
        # If we're skipping this class block, skip this line
        if skip_block and (class_match or attr_match):
            continue
        
        # Check for references to external classes
        ref_match = ref_pattern.match(line)
        if ref_match:
            target_class = ref_match.group(3)
            if target_class not in allowed_classes:
                continue
        
        # Reset skip_block when we hit an empty line (end of class block)
        if not line.strip():
            skip_block = False
            current_class = None
        
        filtered_lines.append(line)
    
    return "\n".join(filtered_lines)


def generate_chunk(state: State, invoke_text: Callable[[str], str]) -> State:
    concepts = state.get("concepts", [])
    idx = state.get("current_index", 0)
    if idx >= len(concepts):
        return {
            "done": True,
            "final_metamodel": "\n\n".join(state.get("approved_chunks", [])),
        }

    concept = concepts[idx]
    approved_chunks = state.get("approved_chunks", [])
    
    other_concepts = [c for c in concepts if c != concept]
    other_concepts_str = ", ".join(other_concepts) if other_concepts else "(none)"
    
    approved_class_names = []
    for chunk in approved_chunks:
        approved_class_names.extend(_chunk_class_names(chunk))
    approved_classes_str = ", ".join(approved_class_names) if approved_class_names else "(none)"
    
    approved_text = "\n\n".join(approved_chunks) if approved_chunks else ""

    feedback = ""
    validation = state.get("current_validation", {})
    human_rejected = state.get("human_approved") is not None and not state.get("human_approved", True)
    if validation and (not validation.get("valid") or human_rejected):
        issues = validation.get("issues", [])
        suggestion = validation.get("suggestion", "")
        issues_text = "\n".join(f"  - {i}" for i in issues)
        feedback = f"\n\nFIX THESE:\n{issues_text}\n{suggestion}\n\n"

    prompt = (
        f"Generate JjScript metamodel for '{concept}' ONLY.\n"
        f"Define ONLY the primary '{concept}' class and its direct attributes/references.\n"
        f"EXCLUDE: {other_concepts_str} — do NOT define their classes.\n"
        f"DO NOT REDEFINE: {approved_classes_str} — these exist, only reference them.\n"
        f"You may reference other classes but DO NOT define them — they will be added later.\n"
        f"Output ONLY the '{concept}' class definition — nothing else.\n"
    )
    if approved_text:
        prompt += f"\nAlready defined (DO NOT REPEAT):\n{approved_text}\n\n"
    if feedback:
        prompt += feedback
    prompt += (
        f"Domain: {state.get('intent_summary', '')}\n"
        f"Concept: {concept}\n"
        "Use PascalCase for classes, camelCase for attributes.\n"
        "Output JjScript only — no markdown."
    )
    new_chunk = invoke_text(prompt)
    
    # Validate: new_chunk must NOT redefine approved classes
    new_chunk_classes = _chunk_class_names(new_chunk)
    forbidden = [cls for cls in new_chunk_classes if cls in approved_class_names]
    if forbidden:
        # Parse chunk into class blocks and filter out forbidden ones
        lines = new_chunk.split("\n")
        kept_blocks = []
        current_block_lines = []
        current_block_class = None
        
        for i, line in enumerate(lines):
            class_match = re.match(r"^\s*create\s+(?:abstract\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)", line, re.IGNORECASE)
            
            if class_match:
                # Save previous block if it was allowed
                if current_block_class and current_block_class not in approved_class_names:
                    kept_blocks.append("\n".join(current_block_lines))
                
                # Start new block
                current_block_class = class_match.group(1)
                current_block_lines = [line]
            elif current_block_class:
                # We're inside a class block
                current_block_lines.append(line)
            else:
                # We're before any class definition
                if line.strip():
                    kept_blocks.append(line)
        
        # Don't forget the last block
        if current_block_class and current_block_class not in approved_class_names:
            kept_blocks.append("\n".join(current_block_lines))
        
        new_chunk = "\n\n".join(kept_blocks).strip()
    
    # Final safety check: ensure no approved classes in final chunk
    final_classes = _chunk_class_names(new_chunk)
    still_forbidden = [cls for cls in final_classes if cls in approved_class_names]
    if still_forbidden:
        # Emergency: just remove all text mentioning those classes
        for cls in still_forbidden:
            new_chunk = re.sub(rf"(?m)^.*\bcreate\s+(?:abstract\s+)?class\s+{cls}\b.*$", "", new_chunk, flags=re.IGNORECASE)
        new_chunk = "\n".join(line for line in new_chunk.split("\n") if line.strip())
    
    # The current_chunk is the CUMULATIVE metamodel: all approved + new
    if approved_chunks:
        cumulative = "\n\n".join([*approved_chunks, new_chunk])
    else:
        cumulative = new_chunk
    return {"current_concept": concept, "current_chunk": cumulative, "current_new_chunk": new_chunk}


def build_sample_model(state: State, invoke_text: Callable[[str], str]) -> str:
    """Generate a concrete sample model (M1) in JJScript that challenges the current chunk."""
    # Use cumulative metamodel because new concept might reference approved classes
    current_chunk = state.get("current_chunk", "")
    prev_sample = state.get("cumulative_sample_model", "")
    concept = state.get("current_concept", "")

    prompt = f"Create ONE instance for '{concept}' that tests the metamodel.\n"
    if prev_sample:
        prompt += f"Previous sample already exists (DO NOT REPEAT IT):\n{prev_sample}\n\n"
        prompt += f"Add ONLY NEW JJScript code for '{concept}' instance.\n"
        prompt += "Link to existing instances from previous sample using their exact names.\n"
    prompt += (
        "CRITICAL: Create ONLY INSTANCES ('create object'), NEVER class definitions ('create class').\n"
        "Use 'create object <ClassName> <name>'.\n"
        "Set attributes using 'set <attr> of <obj> to <value>'.\n"
        "For missing referenced classes, create placeholder instances if needed.\n"
        "DO NOT add any explanatory text or descriptions.\n"
        "Output ONLY raw JJScript commands, nothing else.\n"
        f"Metamodel:\n{current_chunk}"
    )
    sample = invoke_text(prompt)
    
    # Extract only JJScript code (remove markdown fences and explanatory text)
    sample_clean = sample
    for fence in ("```jjscript", "```python", "```"):
        sample_clean = sample_clean.replace(fence, "")
    
    # Only keep lines that are actual JJScript commands or comments
    lines = sample_clean.split("\n")
    code_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # STRICT filter: only keep lines that start with JJScript keywords
        if (stripped.startswith("#") or
            stripped.lower().startswith("create object ") or
            stripped.lower().startswith("create class ") or
            stripped.lower().startswith("create attribute ") or
            stripped.lower().startswith("create reference ") or
            stripped.lower().startswith("create containment ") or
            stripped.lower().startswith("set ") or
            stripped.lower().startswith("add ")):
            code_lines.append(line)
    
    sample_code = "\n".join(code_lines).strip()
    
    return sample_code


def build_isolated_sample_model(state: State, invoke_text: Callable[[str], str]) -> str:
    """Generate a sample model that tests ONLY the primary concept class — no other classes."""
    current_chunk = state.get("current_new_chunk", "")
    concept = state.get("current_concept", "")
    all_classes = _chunk_class_names(current_chunk)
    
    # Only allow classes that match the concept name
    allowed = [cls for cls in all_classes if concept.lower() in cls.lower() or cls.lower() in concept.lower()]
    if not allowed:
        allowed = all_classes[:1] if all_classes else []
    
    allowed_str = ", ".join(allowed) if allowed else "(none)"

    prompt = (
        f"Create ONE instance for '{concept}' ONLY.\n"
        f"Allowed classes: {allowed_str}.\n"
        "Use 'create object <Class> <name>'.\n"
        "Set ALL non-reference attributes using CORRECT syntax: 'set <attr> of <obj> to <value>'.\n"
        "DO NOT use 'set obj.attr = value' syntax — that's WRONG.\n"
        "DO NOT set references to other classes.\n"
        "DO NOT add explanations or descriptions.\n"
        "Output ONLY raw JJScript commands.\n"
        f"Chunk:\n{current_chunk}"
    )
    sample = invoke_text(prompt)
    
    # Extract only JJScript code - use same strict filter as regular samples
    sample_clean = sample
    for fence in ("```jjscript", "```python", "```"):
        sample_clean = sample_clean.replace(fence, "")
    
    lines = sample_clean.split("\n")
    code_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # STRICT filter: only keep lines that start with JJScript keywords
        if (stripped.startswith("#") or
            stripped.lower().startswith("create object ") or
            stripped.lower().startswith("set ") or
            stripped.lower().startswith("add ")):
            code_lines.append(line)
    
    sample_code = "\n".join(code_lines).strip()
    
    return sample_code


def validate_chunk(state: State, sample_model: str, invoke_json: Callable[[str], dict]) -> dict:
    current = state.get("current_chunk", "")
    concept = state.get("current_concept", "")
    return invoke_json(
        f"Validate if chunk for '{concept}' can represent the sample.\n"
        "Mark valid=false if major aspects missing.\n"
        "JSON keys: valid (bool), issues (array), suggestion (string).\n\n"
        f"Chunk:\n{current}\n\nSample:\n{sample_model}"
    )


def validate_isolated_chunk(state: State, sample_model: str, invoke_json: Callable[[str], dict]) -> dict:
    current = state.get("current_new_chunk", "")
    concept = state.get("current_concept", "")
    allowed = _chunk_class_names(current)
    allowed_str = ", ".join(allowed) if allowed else "(none)"
    return invoke_json(
        f"Validate isolated '{concept}' chunk.\n"
        f"Allowed classes: {allowed_str}.\n"
        "Mark valid=false if sample uses other classes or major gaps.\n"
        "JSON keys: valid (bool), issues (array), suggestion (string).\n\n"
        f"Chunk:\n{current}\n\nSample:\n{sample_model}"
    )


def build_challenge_sample_model(state: State, invoke_text: Callable[[str], str], challenge_level: str) -> str:
    """Generate sample model with different complexity levels to challenge the metamodel."""
    current_chunk = state.get("current_chunk", "")
    concept = state.get("current_concept", "")
    
    base_prompt = f"Create instances for '{concept}' that test the metamodel"
    
    if challenge_level == "easy":
        challenge_prompt = (
            "Create SIMPLE instances with basic attributes set.\n"
            "Use straightforward values and minimal relationships.\n"
            "Test only core functionality of the classes."
        )
    elif challenge_level == "moderate":
        challenge_prompt = (
            "Create instances with COMPLEX relationships and edge cases.\n"
            "Use realistic but challenging attribute values.\n"
            "Test inheritance and reference constraints."
        )
    else:  # hard
        challenge_prompt = (
            "Create instances that STRESS TEST the metamodel.\n"
            "Use boundary values, complex hierarchies, and multiple relationships.\n"
            "Test all possible constraints and edge cases.\n"
            "Try to find gaps in the metamodel definition."
        )
    
    prompt = (
        f"{base_prompt}.\n\n{challenge_prompt}\n\n"
        "CRITICAL: Create ONLY INSTANCES ('create object'), NEVER class definitions.\n"
        "Use 'create object <ClassName> <name>'.\n"
        "Set attributes using 'set <attr> of <obj> to <value>'.\n"
        "Output ONLY raw JJScript commands, nothing else.\n"
        f"Metamodel:\n{current_chunk}"
    )
    
    sample = invoke_text(prompt)
    
    # Clean the sample (same as original build_sample_model)
    sample_clean = sample
    for fence in ("```jjscript", "```python", "```"):
        sample_clean = sample_clean.replace(fence, "")
    
    lines = sample_clean.split("\n")
    code_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if (stripped.startswith("#") or
            stripped.lower().startswith("create object ") or
            stripped.lower().startswith("set ") or
            stripped.lower().startswith("add ")):
            code_lines.append(line)
    
    return "\n".join(code_lines).strip()


def analyze_file_content(state: State, invoke_json: Callable[[str], dict]) -> dict:
    """Analyze attached file content to identify concepts and highlight coverage."""
    file_content = state.get("attached_file_content", "")
    if not file_content:
        return {"analysis": "No file content provided", "missing_concepts": [], "highlighted_positions": {}}
    
    concepts = state.get("concepts", [])
    approved_chunks = state.get("approved_chunks", [])
    current_chunk = state.get("current_chunk", "")
    
    metamodel_content = "\n\n".join([*approved_chunks, current_chunk]) if approved_chunks else current_chunk
    
    prompt = (
        f"Analyze this file content against the metamodel concepts.\n"
        f"Current concepts being modeled: {', '.join(concepts)}\n\n"
        f"Current metamodel:\n{metamodel_content}\n\n"
        f"File content to analyze:\n{file_content}\n\n"
        "Identify:\n"
        "1. Which concepts from the metamodel are present in the file\n"
        "2. What concepts are missing but should be there\n"
        "3. What new concepts in the file are not covered by the metamodel\n"
        "4. Provide character positions where each concept appears\n\n"
        "Return JSON with keys:\n"
        "- covered_concepts: array of concept names found\n"
        "- missing_concepts: array of concepts that should be added\n"
        "- new_concepts: array of concepts found but not in metamodel\n"
        "- concept_positions: object mapping concept names to arrays of {start, end, text} positions\n"
        "- coverage_percentage: number (0-100)\n"
        "- analysis: string summary"
    )
    
    return invoke_json(prompt)


def validate_with_file_analysis(state: State, invoke_json: Callable[[str], dict]) -> dict:
    """Validate metamodel against attached file content analysis."""
    file_analysis = state.get("file_analysis_validation", {})
    if not file_analysis:
        return {"valid": True, "issues": [], "suggestion": "No file analysis available"}
     
    missing_concepts = file_analysis.get("missing_concepts", [])
    coverage_percentage = file_analysis.get("coverage_percentage", 0)
    
    issues = []
    if missing_concepts:
        issues.append(f"Missing concepts from file: {', '.join(missing_concepts)}")
    
    if coverage_percentage < 70:
        issues.append(f"Low concept coverage: {coverage_percentage}% (should be >70%)")
    
    valid = len(issues) == 0
    
    suggestion = ""
    if missing_concepts:
        suggestion = f"Consider adding these concepts to the metamodel: {', '.join(missing_concepts[:3])}"
    
    return {
        "valid": valid,
        "issues": issues,
        "suggestion": suggestion,
        "file_coverage": coverage_percentage,
        "missing_from_file": missing_concepts
    }


def dual_validation(
    state: State,
    invoke_text: Callable[[str], str],
    invoke_json: Callable[[str], dict],
    validator_invoke_text: Callable[[str], str] | None = None,
    validator_invoke_json: Callable[[str], dict] | None = None,
    user_responder: Callable[[str, dict], str] | None = None,
) -> State:
    validation_text = validator_invoke_text or invoke_text
    validation_json = validator_invoke_json or invoke_json
    
    # Ask user for challenge level
    challenge_level = "moderate"  # default
    if user_responder:
        challenge_question = (
            "Choose validation challenge level:\n"
            "1. Easy - Simple instances with basic attributes\n"
            "2. Moderate - Complex relationships and realistic values\n"
            "3. Hard - Stress test with boundary values and edge cases\n"
            "Which level do you want? (easy/moderate/hard)"
        )
        response = user_responder(challenge_question, {"validation_stage": "challenge_selection"})
        if response.lower() in ["easy", "1"]:
            challenge_level = "easy"
        elif response.lower() in ["hard", "3"]:
            challenge_level = "hard"
    
    # Generate challenge-based sample model
    sample_model = build_challenge_sample_model(state, validation_text, challenge_level)
    validation = validate_chunk(state, sample_model, validation_json)
    
    # Check for file-based validation if file is attached
    updates = {
        "current_sample_model": sample_model,
        "current_validation": validation,
        "validation_challenge_level": challenge_level,
        "wants_isolated_validation": False,
    }
    
    if state.get("attached_file_content"):
        file_analysis = analyze_file_content(state, validation_json)
        file_validation = validate_with_file_analysis(state, validation_json)
        
        # Merge validations
        merged_validation = {
            "valid": validation.get("valid", False) and file_validation.get("valid", False),
            "issues": [*validation.get("issues", []), *file_validation.get("issues", [])],
            "suggestion": f"{validation.get('suggestion', '')}\n\n{file_validation.get('suggestion', '')}".strip(),
            "challenge_validation": validation,
            "file_validation": file_validation
        }
        
        updates.update({
            "current_validation": merged_validation,
            "file_analysis_validation": file_analysis,
        })
    
    return updates


def isolated_validation_step(
    state: State,
    invoke_text: Callable[[str], str],
    invoke_json: Callable[[str], dict],
    user_responder: Callable[[str, dict], str] | None = None,
    human_validator: Callable[[dict], bool] | None = None,
    validator_invoke_text: Callable[[str], str] | None = None,
    validator_invoke_json: Callable[[str], dict] | None = None,
) -> State:
    """After human sees the normal validation, optionally run isolated validation."""
    if state.get("current_index", 0) == 0 or not user_responder:
        return {}

    answer = user_responder(
        "Do you want an isolated validation of the chunk itself?",
        {
            "current_concept": state.get("current_concept", ""),
            "validation_stage": "after_human_validate",
        },
    )
    wants_isolated = answer.strip().lower() in {"y", "yes"}
    if not wants_isolated:
        return {"wants_isolated_validation": False}

    validation_text = validator_invoke_text or invoke_text
    validation_json = validator_invoke_json or invoke_json

    isolated_sample_model = build_isolated_sample_model(state, validation_text)
    isolated_validation = validate_isolated_chunk(state, isolated_sample_model, validation_json)

    cumulative_validation = state.get("current_validation", {})
    merged_validation = {
        "valid": bool(cumulative_validation.get("valid", False)) and bool(isolated_validation.get("valid", False)),
        "issues": [
            *cumulative_validation.get("issues", []),
            *[f"[isolated] {issue}" for issue in isolated_validation.get("issues", [])],
        ],
        "suggestion": "\n\n".join(
            part for part in [
                cumulative_validation.get("suggestion", ""),
                isolated_validation.get("suggestion", ""),
            ] if part
        ),
        "cumulative_validation": cumulative_validation,
        "isolated_validation": isolated_validation,
    }

    updates: State = {
        "wants_isolated_validation": True,
        "current_isolated_sample_model": isolated_sample_model,
        "current_isolated_validation": isolated_validation,
        "current_validation": merged_validation,
    }

    if human_validator:
        chunk_to_show = state.get("current_new_chunk", "")
        chunk_classes = _chunk_class_names(chunk_to_show)
        concept = state.get("current_concept", "")
        
        # For isolated view, only show classes that match the concept name
        primary_classes = [cls for cls in chunk_classes if concept.lower() in cls.lower() or cls.lower() in concept.lower()]
        if not primary_classes:
            # Fallback: if no match, just use first class
            primary_classes = chunk_classes[:1] if chunk_classes else []
        
        # Filter chunk to only show primary classes
        filtered_chunk = _filter_chunk_for_isolated_display(chunk_to_show, primary_classes)
        
        payload = {
            "concept": state.get("current_concept", "") + " (isolated)",
            "chunk": filtered_chunk,   # filtered chunk showing only primary concept class
            "sample_model": isolated_sample_model,
            "validation": isolated_validation,
        }
        isolated_approved = human_validator(payload)
        if not isolated_approved:
            updates["human_approved"] = False

    return updates


def human_validate(state: State, human_validator: Callable[[dict], bool] | None) -> State:
    # Show CUMULATIVE chunk and CUMULATIVE sample for full context
    cumulative_chunk = state.get("current_chunk", "")  # All approved + new
    new_chunk = state.get("current_new_chunk", "")     # Just this concept
    chunk_classes = _chunk_class_names(cumulative_chunk)
    
    # Build cumulative sample (previous + new) for display
    new_sample = state.get("current_sample_model", "")
    prev_cumulative = state.get("cumulative_sample_model", "")
    if prev_cumulative:
        cumulative_sample_display = prev_cumulative + "\n\n" + new_sample
    else:
        cumulative_sample_display = new_sample
    
    payload = {
        "concept": state.get("current_concept", ""),
        "chunk": cumulative_chunk,              # CUMULATIVE chunk (all classes)
        "sample_model": cumulative_sample_display,  # CUMULATIVE sample (all instances)
        "validation": state.get("current_validation", {}),
    }
    
    # Add file analysis if available
    if state.get("file_analysis_validation"):
        payload["file_analysis"] = state["file_analysis_validation"]
    
    approved = human_validator(payload) if human_validator else True
    
    # Still store only the NEW chunk as validated (for accumulation)
    validated_chunk = state.get("current_new_chunk", "")
    
    return {
        "human_approved": approved,
        "current_validated_chunk": validated_chunk,
    }


def advance(state: State) -> State:
    max_retries = 3
    human_approved = bool(state.get("human_approved", False))
    if human_approved:
        validated_chunk = state.get("current_validated_chunk", state.get("current_new_chunk", state.get("current_chunk", "")))
        approved_chunks = [*state.get("approved_chunks", []), validated_chunk]
        next_idx = state.get("current_index", 0) + 1
        done = next_idx >= len(state.get("concepts", []))
        
        # Build cumulative sample: append new sample to previous samples
        new_sample = state.get("current_sample_model", "")
        prev_cumulative = state.get("cumulative_sample_model", "")
        
        if prev_cumulative:
            cumulative_sample = prev_cumulative + "\n\n" + new_sample
        else:
            cumulative_sample = new_sample
        
        return {
            "approved_chunks": approved_chunks,
            "current_index": next_idx,
            "concept_retry_count": 0,
            "done": done,
            "cumulative_sample_model": cumulative_sample,
            "final_metamodel": "\n\n".join(approved_chunks) if done else "",
        }

    retry_count = state.get("concept_retry_count", 0) + 1
    if retry_count >= max_retries:
        next_idx = state.get("current_index", 0) + 1
        done = next_idx >= len(state.get("concepts", []))
        return {
            "current_index": next_idx,
            "concept_retry_count": 0,
            "done": done,
            "final_metamodel": "\n\n".join(state.get("approved_chunks", [])) if done else "",
        }

    return {"concept_retry_count": retry_count}


def router(state: State) -> str:
    return "end" if state.get("done", False) else "next"