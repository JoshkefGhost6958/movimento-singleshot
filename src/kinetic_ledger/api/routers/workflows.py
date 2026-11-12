workflow_states: Dict[str, Dict[str, Any]] = {}


class WorkflowStepUpdate(BaseModel):
    """Workflow step update model"""
    step_id: str
    status: str  # 'pending', 'processing', 'success', 'error', 'review'
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


class WorkflowState(BaseModel):
    """Complete workflow state model"""
    correlation_id: str
    status: str  # 'pending', 'processing', 'completed', 'failed'
    current_step: Optional[str] = None
    steps: List[WorkflowStepUpdate]
    ingest_data: Optional[Dict[str, Any]] = None
    gemini_data: Optional[Dict[str, Any]] = None
    oracle_data: Optional[Dict[str, Any]] = None
    routing_data: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


@app.get("/api/workflows/{correlation_id}", response_model=WorkflowState)
def get_workflow_state(correlation_id: str):
    """
    Get complete workflow state for a given correlation ID.
    
    Returns all step data, current progress, and detailed information
    for each stage of the trustless agent loop.
    
    Args:
        correlation_id: Unique identifier for workflow execution
    
    Returns:
        WorkflowState with complete step history and data
    
    Raises:
        HTTPException: 404 if workflow not found
    """
    logger.info(f"[GET /api/workflows/{correlation_id}] Fetching workflow state")
    
    if correlation_id not in workflow_states:
        logger.warning(f"[GET /api/workflows/{correlation_id}] Workflow not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {correlation_id} not found"
        )
    
    workflow = workflow_states[correlation_id]
    logger.info(f"[GET /api/workflows/{correlation_id}] Returning workflow state")
    
    return workflow


@app.get("/api/workflows")
def list_workflows(
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None
):
    """
    List all workflows with optional filtering.
    
    Args:
        limit: Maximum number of workflows to return (default: 50)
        offset: Number of workflows to skip (default: 0)
        status_filter: Filter by workflow status (optional)
    
    Returns:
        List of workflow summaries
    """
    logger.info(f"[GET /api/workflows] Listing workflows (limit={limit}, offset={offset})")
    
    workflows = list(workflow_states.values())
    
    # Apply status filter if provided
    if status_filter:
        workflows = [w for w in workflows if w.get('status') == status_filter]
    
    # Apply pagination
    total = len(workflows)
    workflows = workflows[offset:offset + limit]
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "workflows": workflows
    }


@app.post("/api/workflows/{correlation_id}/steps")
def update_workflow_step(
    correlation_id: str,
    step_update: WorkflowStepUpdate
):
    """
    Update a specific workflow step (internal use for step tracking).
    
    Args:
        correlation_id: Workflow identifier
        step_update: Step update data
    
    Returns:
        Updated workflow state
    """
    logger.info(
        f"[POST /api/workflows/{correlation_id}/steps] "
        f"Updating step {step_update.step_id} to {step_update.status}"
    )
    
    # Initialize workflow if not exists
    if correlation_id not in workflow_states:
        from datetime import datetime
        workflow_states[correlation_id] = {
            "correlation_id": correlation_id,
            "status": "processing",
            "current_step": step_update.step_id,
            "steps": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
    
    workflow = workflow_states[correlation_id]
    
    # Update or add step
    existing_step = next(
        (s for s in workflow["steps"] if s.get("step_id") == step_update.step_id),
        None
    )
    
    if existing_step:
        existing_step.update(step_update.dict())
    else:
        workflow["steps"].append(step_update.dict())
    
    # Update workflow metadata
    workflow["current_step"] = step_update.step_id
    from datetime import datetime
    workflow["updated_at"] = datetime.utcnow().isoformat()
    
    # Update overall workflow status based on steps
    if step_update.status == "error":
        workflow["status"] = "failed"
    elif all(s.get("status") == "success" for s in workflow["steps"]):
        workflow["status"] = "completed"
    else:
        workflow["status"] = "processing"
    
    return workflow


@app.get("/api/metrics/{blend_id}/timeline")
def get_metrics_timeline(blend_id: str):
    """
    Get frame-by-frame quality metrics timeline for a blend.
    
    Returns detailed metrics data for visualization:
    - Coverage values per 30-frame window
    - Local/Global diversity scores
    - Per-joint L2 velocity and acceleration
    - Quality tier progression
    
    Args:
        blend_id: Unique identifier for the blend
    
    Returns:
        Metrics timeline data for charts
    
    Raises:
        HTTPException: 404 if blend not found
    """
    logger.info(f"[GET /api/metrics/{blend_id}/timeline] Fetching metrics timeline")
    
    try:
        # Load real metrics from artifact metadata
        artifacts_dir = Path("artifacts") / blend_id
        metadata_file = artifacts_dir / "metadata.json"
        dynamics_file = artifacts_dir / "joint_dynamics.json"
        
        if not metadata_file.exists():
            raise HTTPException(404, f"Blend not found: {blend_id}")
        
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
        
        # Load joint dynamics if available
        joint_dynamics = {}
        if dynamics_file.exists():
            with open(dynamics_file, 'r') as f:
                joint_dynamics = json.load(f)
        
        # Extract real metrics from metadata
        aggregate_metrics = metadata.get("aggregate_metrics", {})
        metrics = metadata.get("metrics", aggregate_metrics)
        
        # Build coverage timeline from actual frame data
        coverage_timeline = []
        frame_files = sorted(artifacts_dir.glob("frame-*.json"))
        for i, frame_file in enumerate(frame_files):
            if i % 30 == 0:  # Sample every 30 frames
                with open(frame_file, 'r') as f:
                    frame_data = json.load(f)
                # Estimate coverage from omega values
                omega = frame_data.get("omega", 0.5)
                coverage_timeline.append(round(0.7 + (omega * 0.3), 2))
        
        # Extract per-joint metrics from joint dynamics
        per_joint_metrics = {}
        if joint_dynamics:
            for joint_name in ["Pelvis", "LeftWrist", "RightWrist", "LeftFoot", "RightFoot"]:
                if joint_name in joint_dynamics.get("joint_names", []):
                    idx = joint_dynamics["joint_names"].index(joint_name)
                    velocities = joint_dynamics.get("l2_velocity", [])
                    accelerations = joint_dynamics.get("l2_acceleration", [])
                    if velocities and accelerations:
                        per_joint_metrics[joint_name] = {
                            "l2_velocity": round(float(velocities[idx]), 4),
                            "l2_acceleration": round(float(accelerations[idx]), 4),
                        }
        
        # If no per-joint metrics from dynamics, use aggregate
        if not per_joint_metrics:
            per_joint_metrics = {
                "Pelvis": {"l2_velocity": metrics.get("l2_velocity", 0.05), "l2_acceleration": metrics.get("l2_acceleration", 0.03)},
            }
        
        # Calculate cost breakdown from real pricing
        quality_tier = metrics.get("quality_tier", "medium")
        quality_rates = {"ultra": 0.25, "high": 0.10, "medium": 0.05, "low": 0.01}
        rate = quality_rates.get(quality_tier, 0.05)
        total_frames = metadata.get("total_artifacts", len(frame_files))
        duration = total_frames / 30
        
        cost_breakdown = {
            "generation_cost": round(rate * duration, 4),
            "quality_premium": round(rate * duration * 0.1, 4),
            "base_fee": 0.010,
        }
        
        return {
            "blend_id": blend_id,
            "coverage_timeline": coverage_timeline or [metrics.get("coverage", 0.85)],
            "diversity": {
                "local": metrics.get("local_diversity", metrics.get("diversity", 2.0)),
                "global": metrics.get("global_diversity", metrics.get("diversity", 3.0)),
            },
            "per_joint_metrics": per_joint_metrics,
            "cost_breakdown": cost_breakdown,
            "quality_tier": quality_tier,
            "total_frames": total_frames,
            "blend_window": [0, total_frames],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to load metrics timeline: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to load metrics timeline: {str(e)}")


@app.get("/api/oracle/{analysis_id}/neighbors")
def get_knn_neighbors(
    analysis_id: str,
    k: int = 15
):
    """
    Get kNN neighbors for an analysis (for Oracle decision visualization).
    
    Args:
        analysis_id: Analysis identifier
        k: Number of neighbors to return (default: 15)
    
    Returns:
        List of nearest neighbors with distances and preview URIs
    
    Raises:
        HTTPException: 404 if analysis not found
    """
    logger.info(f"[GET /api/oracle/{analysis_id}/neighbors] Fetching kNN neighbors (k={k})")
    
    try:
        # Use real vector store from attestation oracle
        from ..services.attestation_oracle import VectorStore
        
        vector_store = VectorStore()
        neighbors = vector_store.get_nearest_neighbors(
            analysis_id=analysis_id,
            k=k,
        )
        
        return {
            "analysis_id": analysis_id,
            "k": k,
            "neighbors": neighbors,
        }
    except Exception as e:
        logger.error(f"Failed to fetch kNN neighbors: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to fetch kNN neighbors: {str(e)}")


# ============================================================================
# Server-Sent Events (SSE) for Real-time Workflow Updates
# ============================================================================

from fastapi.responses import StreamingResponse
import asyncio


# Global workflow states storage
workflow_states = {}


async def simulate_blend_workflow(correlation_id: str):
    """Simulate blend generation workflow with progressive updates."""
    steps = [
        ("analyzing_prompt", "Analyzing prompt", 1),
        ("loading_motions", "Loading motion data", 2),
        ("computing_blend", "Computing blend weights", 3),
        ("generating_metrics", "Generating quality metrics", 4),
        ("creating_transaction", "Creating blockchain transaction", 5),
        ("completed", "Blend completed", 6)
    ]
    
    for step_name, step_desc, progress in steps:
        await asyncio.sleep(1.5)  # Simulate processing time
        
        if correlation_id in workflow_states:
            workflow_states[correlation_id].update({
                "current_step": step_name,
                "current_step_name": step_desc,
                "progress": progress,
                "status": "completed" if step_name == "completed" else "processing",
                "updated_at": uuid.uuid4().hex
            })
            
            # Add metrics on the metrics step
            if step_name == "generating_metrics":
                workflow_states[correlation_id]["metrics"] = {
                    "coverage": 0.85 + (progress * 0.02),
                    "local_diversity": 0.78,
                    "global_diversity": 0.82,
                    "l2_velocity": 0.06,
                    "l2_acceleration": 0.035,
                    "quality_tier": "high"
                }
            
            # Add transaction on final step
            if step_name == "completed":
                workflow_states[correlation_id]["settlement"] = {
                    "tx_hash": f"0x{uuid.uuid4().hex}{uuid.uuid4().hex[:32]}",
                    "timestamp": int(uuid.uuid4().int % 1000000000)
                }


async def simulate_npc_workflow(correlation_id: str):
    """Simulate NPC spawn workflow with progressive updates."""
    steps = [
        ("loading_motion", "Loading motion blend", 1),
        ("creating_character", "Creating character mesh", 2),
        ("spawning_on_chain", "Spawning NPC on Arc Network", 3),
        ("completed", "NPC spawned successfully", 4)
    ]
    
    for step_name, step_desc, progress in steps:
        await asyncio.sleep(1)
        
        if correlation_id in workflow_states:
            workflow_states[correlation_id].update({
                "current_step": step_name,
                "current_step_name": step_desc,
                "progress": progress,
                "status": "completed" if step_name == "completed" else "processing",
                "updated_at": uuid.uuid4().hex
            })
            
            if step_name == "completed":
                workflow_states[correlation_id]["settlement"] = {
                    "tx_hash": f"0x{uuid.uuid4().hex}{uuid.uuid4().hex[:32]}",
                    "timestamp": int(uuid.uuid4().int % 1000000000)
                }


async def workflow_event_generator(correlation_id: str):
    """
    Generate Server-Sent Events for workflow updates.
    
    Streams real-time updates as workflow progresses through steps.
    """
    logger.info(f"[SSE /api/workflows/{correlation_id}/stream] Client connected")
    
    last_update = None
    
    try:
        while True:
            if correlation_id in workflow_states:
                workflow = workflow_states[correlation_id]
                current_update = workflow.get("updated_at")
                
                # Send update if workflow changed
                if current_update != last_update:
                    last_update = current_update
                    
                    yield f"data: {json.dumps(workflow)}\n\n"
                
                # Stop streaming if workflow completed or failed
                if workflow.get("status") in ["completed", "failed"]:
                    logger.info(
                        f"[SSE /api/workflows/{correlation_id}/stream] "
                        f"Workflow {workflow.get('status')}, closing stream"
                    )
                    break
            
            await asyncio.sleep(0.5)  # Poll every 500ms for responsiveness
            
    except asyncio.CancelledError:
        logger.info(f"[SSE /api/workflows/{correlation_id}/stream] Client disconnected")


@app.get("/api/blend/{correlation_id}/stream")
async def stream_blend_updates(correlation_id: str):
    """
    Stream real-time blend generation updates via Server-Sent Events (SSE).
    
    Clients subscribe to receive live updates as the blend progresses.
    """
    logger.info(f"[GET /api/blend/{correlation_id}/stream] Starting SSE stream")
    
    # Start background workflow simulation
    asyncio.create_task(simulate_blend_workflow(correlation_id))
    
    return StreamingResponse(
        workflow_event_generator(correlation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/npc/{correlation_id}/stream")
async def stream_npc_updates(correlation_id: str):
    """
    Stream real-time NPC spawn updates via Server-Sent Events (SSE).
    
    Clients subscribe to receive live updates as the NPC spawns.
    """
    logger.info(f"[GET /api/npc/{correlation_id}/stream] Starting SSE stream")
    
    # Start background workflow simulation
    asyncio.create_task(simulate_npc_workflow(correlation_id))
    
    return StreamingResponse(
        workflow_event_generator(correlation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/workflows/{correlation_id}/stream")
async def stream_workflow_updates(correlation_id: str):
    """
    Stream real-time workflow updates via Server-Sent Events (SSE).
    
    Clients can subscribe to receive live updates as the workflow progresses
    through each step of the trustless agent loop.
    
    Args:
        correlation_id: Workflow identifier
    
    Returns:
        StreamingResponse with SSE data
    """
    logger.info(f"[GET /api/workflows/{correlation_id}/stream] Starting SSE stream")
    
    return StreamingResponse(
        workflow_event_generator(correlation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

@app.get("/api/workflows/{correlation_id}/stream")
async def stream_workflow_updates(correlation_id: str):
    """
    Stream real-time workflow updates via Server-Sent Events (SSE).
    
    Clients can subscribe to receive live updates as the workflow progresses
    through each step of the trustless agent loop.
    
    Args:
        correlation_id: Workflow identifier
    
    Returns:
        StreamingResponse with SSE data
    """
    logger.info(f"[GET /api/workflows/{correlation_id}/stream] Starting SSE stream")
    
    return StreamingResponse(
        workflow_event_generator(correlation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )