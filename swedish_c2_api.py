#!/usr/bin/env python3
"""
SWEDISH C2 API SERVICE
FastAPI wrapper for Swedish Integrated Air Defense Doctrine Service
Exposes HTTP endpoints for multi-domain C2 integration

Usage:
    pip install fastapi uvicorn
    uvicorn swedish_c2_api:app --host 0.0.0.0 --port 8002 --reload

Created by: Joel Trout & Erik Andersson
For: Swedish Armed Forces / FOI validation
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
import time

# Import the doctrine service
from swedish_c2_doctrine import (
    SensorContact, MultiSensorThreat, AvailableAsset, OperationalContext,
    SwedishC2Service, ThreatType, SystemType, ContactPriority, SensorSource
)

app = FastAPI(
    title="Swedish C2 API Service",
    description="Multi-domain air defense decision support for Swedish Armed Forces",
    version="1.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# PYDANTIC MODELS FOR API
# ============================================================================

class SensorContactAPI(BaseModel):
    source: str = Field(..., description="Sensor source (9LV/GBA_C2/BMS/NATO_AWE/Visual)")
    track_id: str = Field(..., description="Track identifier")
    bearing: int = Field(..., ge=0, le=360, description="Bearing in degrees")
    range_nm: float = Field(..., ge=0, description="Range in nautical miles")
    altitude_m: int = Field(..., ge=0, description="Altitude in meters")
    speed_knots: float = Field(..., ge=0, description="Speed in knots")
    confidence: float = Field(..., ge=0, le=1, description="Confidence 0-1")
    classification: str = Field(..., description="Target classification")
    iff_response: Optional[str] = None
    data_age_seconds: int = Field(default=0, ge=0)
    ecm_detected: bool = Field(default=False)
    platform_name: Optional[str] = None

class MultiSensorThreatAPI(BaseModel):
    contacts: List[SensorContactAPI]
    threat_type: str = Field(..., description="Threat type")
    priority: str = Field(..., description="Contact priority (Critical/High/Medium/Low)")
    estimated_bearing: int = Field(..., ge=0, le=360)
    estimated_range_nm: float = Field(..., ge=0)
    time_to_boundary_minutes: float = Field(..., ge=0)
    target_description: str

class AvailableAssetAPI(BaseModel):
    system_type: str = Field(..., description="System type")
    count: int = Field(..., ge=1)
    ready_state: str = Field(..., description="READY/STANDBY_15MIN/MAINTENANCE")
    effective_range_km: float = Field(..., ge=0)
    response_time_minutes: int = Field(..., ge=0)
    cost_per_engagement: int = Field(..., ge=0, description="Cost in SEK")
    success_rate: float = Field(..., ge=0, le=1)
    location: str
    requires_nato_clearance: bool = Field(default=False)
    requires_swedish_clearance: bool = Field(default=True)

class OperationalContextAPI(BaseModel):
    location: str
    weather: str
    visibility_km: float = Field(..., ge=0)
    nato_air_policing_active: bool = False
    allied_aircraft_in_area: bool = False
    civilian_traffic_nearby: bool = False
    strategic_assets_nearby: List[str] = Field(default_factory=list)
    expected_follow_on_activity: bool = False
    historical_pattern: str = ""

class C2Request(BaseModel):
    threat: MultiSensorThreatAPI
    assets: List[AvailableAssetAPI]
    context: OperationalContextAPI

class RecommendationResponse(BaseModel):
    rank: int
    coherence: float
    title: str
    description: str
    template_id: str
    estimated_cost_sek: int
    estimated_success_rate: float
    assets_used: List[str]
    nato_coordination: bool
    swedish_sovereignty: bool
    recommendation_level: str

class C2Response(BaseModel):
    success: bool
    generation_time_ms: float
    arbiter_latency_ms: float
    total_time_ms: float
    options_generated: int
    ranked_recommendations: List[RecommendationResponse]
    threat_summary: Dict[str, Any]
    error: Optional[str] = None

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def convert_sensor_source(source_str: str) -> SensorSource:
    """Convert string to SensorSource enum"""
    mapping = {
        "9LV": SensorSource.NAVAL_9LV,
        "GBA_C2": SensorSource.AIR_DEFENSE_GBA,
        "BMS": SensorSource.GROUND_BMS,
        "NATO_AWE": SensorSource.NATO_AWE,
        "Visual": SensorSource.VISUAL_SOF,
    }
    return mapping.get(source_str, SensorSource.GROUND_BMS)

def convert_threat_type(threat_str: str) -> ThreatType:
    """Convert string to ThreatType enum"""
    mapping = {
        "Transport Aircraft": ThreatType.AIRCRAFT_TRANSPORT,
        "Fighter Aircraft": ThreatType.AIRCRAFT_FIGHTER,
        "Reconnaissance Aircraft": ThreatType.AIRCRAFT_RECONNAISSANCE,
        "Helicopter": ThreatType.HELICOPTER,
        "Cruise Missile": ThreatType.CRUISE_MISSILE,
        "Medium UAV": ThreatType.DRONE_MEDIUM,
        "Small UAV": ThreatType.DRONE_SMALL,
    }
    return mapping.get(threat_str, ThreatType.UNKNOWN)

def convert_system_type(system_str: str) -> SystemType:
    """Convert string to SystemType enum"""
    mapping = {
        "JAS 39 Gripen QRA": SystemType.GRIPEN_QRA,
        "GBA C2 IRIS-T": SystemType.GBA_C2_IRIS_T,
        "GBA C2 RBS 70": SystemType.GBA_C2_RBS_70,
        "9LV Naval System": SystemType.NAVAL_9LV,
        "RBS 70 MANPADS": SystemType.RBS_70,
        "Patriot Battery (NATO)": SystemType.PATRIOT_BATTERY,
        "Electronic Warfare System": SystemType.ELECTRONIC_WARFARE,
    }
    return mapping.get(system_str, SystemType.GBA_C2_IRIS_T)

def convert_contact_priority(priority_str: str) -> ContactPriority:
    """Convert string to ContactPriority enum"""
    mapping = {
        "Critical": ContactPriority.CRITICAL,
        "High": ContactPriority.HIGH,
        "Medium": ContactPriority.MEDIUM,
        "Low": ContactPriority.LOW,
    }
    return mapping.get(priority_str, ContactPriority.MEDIUM)

def api_to_doctrine_models(request: C2Request) -> tuple:
    """Convert API models to Doctrine Service models"""
    
    # Convert sensor contacts
    contacts = []
    for contact_api in request.threat.contacts:
        contacts.append(SensorContact(
            source=convert_sensor_source(contact_api.source),
            track_id=contact_api.track_id,
            bearing=contact_api.bearing,
            range_nm=contact_api.range_nm,
            altitude_m=contact_api.altitude_m,
            speed_knots=contact_api.speed_knots,
            confidence=contact_api.confidence,
            classification=contact_api.classification,
            iff_response=contact_api.iff_response,
            data_age_seconds=contact_api.data_age_seconds,
            ecm_detected=contact_api.ecm_detected,
            platform_name=contact_api.platform_name
        ))
    
    # Convert threat
    threat = MultiSensorThreat(
        contacts=contacts,
        threat_type=convert_threat_type(request.threat.threat_type),
        priority=convert_contact_priority(request.threat.priority),
        estimated_bearing=request.threat.estimated_bearing,
        estimated_range_nm=request.threat.estimated_range_nm,
        time_to_boundary_minutes=request.threat.time_to_boundary_minutes,
        target_description=request.threat.target_description
    )
    
    # Convert assets
    assets = []
    for asset_api in request.assets:
        assets.append(AvailableAsset(
            system_type=convert_system_type(asset_api.system_type),
            count=asset_api.count,
            ready_state=asset_api.ready_state,
            effective_range_km=asset_api.effective_range_km,
            response_time_minutes=asset_api.response_time_minutes,
            cost_per_engagement=asset_api.cost_per_engagement,
            success_rate=asset_api.success_rate,
            location=asset_api.location,
            requires_nato_clearance=asset_api.requires_nato_clearance,
            requires_swedish_clearance=asset_api.requires_swedish_clearance
        ))
    
    # Convert context
    context = OperationalContext(
        location=request.context.location,
        weather=request.context.weather,
        visibility_km=request.context.visibility_km,
        nato_air_policing_active=request.context.nato_air_policing_active,
        allied_aircraft_in_area=request.context.allied_aircraft_in_area,
        civilian_traffic_nearby=request.context.civilian_traffic_nearby,
        strategic_assets_nearby=request.context.strategic_assets_nearby,
        expected_follow_on_activity=request.context.expected_follow_on_activity,
        historical_pattern=request.context.historical_pattern
    )
    
    return threat, assets, context

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Swedish C2 API",
        "status": "operational",
        "version": "1.0",
        "for": "Swedish Armed Forces / FOI",
        "endpoints": [
            "/v1/c2 - Process multi-domain C2 scenario",
            "/health - Service health check",
            "/api/validate-baltic - Run Baltic Sea validation"
        ]
    }

@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "arbiter_service": "connected",
        "doctrine_templates": 6,
        "integration": ["9LV", "GBA C2", "BMS", "NATO"],
        "timestamp": time.time()
    }

@app.post("/v1/c2", response_model=C2Response)
async def process_c2_scenario(request: C2Request):
    """
    Process a multi-domain C2 scenario and return ranked recommendations.
    
    This endpoint:
    1. Accepts multi-sensor threat data, available assets, and operational context
    2. Generates tactical options using Swedish doctrine templates
    3. Evaluates options with ARBITER for semantic coherence
    4. Returns ranked recommendations maintaining Swedish sovereignty
    """
    
    try:
        # Convert API models to Doctrine Service models
        threat, assets, context = api_to_doctrine_models(request)
        
        # Initialize C2 service
        service = SwedishC2Service(arbiter_url="http://0.0.0.0:8000/v1/compare")
        
        # Process scenario
        result = service.process_multi_sensor_scenario(
            threat=threat,
            assets=assets,
            context=context
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=result.get('error', 'C2 service processing failed')
            )
        
        # Convert to response format
        recommendations = [
            RecommendationResponse(
                rank=rec['rank'],
                coherence=rec['coherence'],
                title=rec['title'],
                description=rec['description'],
                template_id=rec['template_id'],
                estimated_cost_sek=rec['estimated_cost_sek'],
                estimated_success_rate=rec['estimated_success_rate'],
                assets_used=rec['assets_used'],
                nato_coordination=rec['nato_coordination'],
                swedish_sovereignty=rec['swedish_sovereignty'],
                recommendation_level=rec['recommendation_level']
            )
            for rec in result['ranked_recommendations']
        ]
        
        return C2Response(
            success=True,
            generation_time_ms=result['generation_time_ms'],
            arbiter_latency_ms=result['arbiter_latency_ms'],
            total_time_ms=result['total_time_ms'],
            options_generated=result['options_generated'],
            ranked_recommendations=recommendations,
            threat_summary=result['threat_summary']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# ============================================================================
# CONVENIENCE ENDPOINTS
# ============================================================================

@app.get("/api/templates")
async def list_templates():
    """List available Swedish doctrine templates"""
    from swedish_c2_doctrine import SwedishAirDefenseDoctrine
    
    templates = []
    for template_id, template_def in SwedishAirDefenseDoctrine.TEMPLATES.items():
        templates.append({
            "id": template_id,
            "title": template_def['title']
        })
    
    return {
        "count": len(templates),
        "templates": templates
    }

@app.get("/api/system-types")
async def get_system_types():
    """Get available Swedish C2 system types"""
    return {
        "systems": [
            "JAS 39 Gripen QRA",
            "GBA C2 IRIS-T",
            "GBA C2 RBS 70",
            "9LV Naval System",
            "RBS 70 MANPADS",
            "Patriot Battery (NATO)",
            "Electronic Warfare System"
        ],
        "sensor_sources": [
            "9LV",
            "GBA_C2",
            "BMS",
            "NATO_AWE",
            "Visual"
        ]
    }

@app.post("/api/validate-baltic")
async def validate_baltic_scenario():
    """
    Run the Baltic Sea validation scenario.
    Unidentified aircraft approaching Gotland with multi-sensor detection.
    """
    
    # Define the scenario
    request = C2Request(
        threat=MultiSensorThreatAPI(
            contacts=[
                SensorContactAPI(
                    source="9LV",
                    track_id="UNKNOWN-47",
                    bearing=95,
                    range_nm=87,
                    altitude_m=8500,
                    speed_knots=420,
                    confidence=0.78,
                    classification="Possible transport aircraft",
                    data_age_seconds=90,
                    platform_name="HMS Karlstad"
                ),
                SensorContactAPI(
                    source="GBA_C2",
                    track_id="AIR-CONTACT-12",
                    bearing=92,
                    range_nm=84,
                    altitude_m=8200,
                    speed_knots=435,
                    confidence=0.85,
                    classification="Medium aircraft, non-standard transponder",
                    iff_response="NON-STANDARD",
                    ecm_detected=True,
                    data_age_seconds=15,
                    platform_name="GBA C2 Gotland"
                ),
                SensorContactAPI(
                    source="BMS",
                    track_id="TRACK-GOLF-7",
                    bearing=98,
                    range_nm=89,
                    altitude_m=8800,
                    speed_knots=410,
                    confidence=0.72,
                    classification="No IFF response, evasive pattern",
                    data_age_seconds=180
                )
            ],
            threat_type="Transport Aircraft",
            priority="High",
            estimated_bearing=95,
            estimated_range_nm=87,
            time_to_boundary_minutes=12.0,
            target_description="Okänt flygplan närmar sig svenskt luftrum från öst"
        ),
        assets=[
            AvailableAssetAPI(
                system_type="JAS 39 Gripen QRA",
                count=2,
                ready_state="STANDBY_15MIN",
                effective_range_km=800,
                response_time_minutes=15,
                cost_per_engagement=200000,
                success_rate=0.95,
                location="F17 Ronneby",
                requires_nato_clearance=False
            ),
            AvailableAssetAPI(
                system_type="GBA C2 IRIS-T",
                count=4,
                ready_state="READY",
                effective_range_km=40,
                response_time_minutes=2,
                cost_per_engagement=500000,
                success_rate=0.93,
                location="Gotland",
                requires_nato_clearance=False
            ),
            AvailableAssetAPI(
                system_type="9LV Naval System",
                count=2,
                ready_state="READY",
                effective_range_km=160,
                response_time_minutes=1,
                cost_per_engagement=1000000,
                success_rate=0.90,
                location="HMS Karlstad",
                requires_nato_clearance=False
            ),
            AvailableAssetAPI(
                system_type="Electronic Warfare System",
                count=1,
                ready_state="READY",
                effective_range_km=50,
                response_time_minutes=0,
                cost_per_engagement=0,
                success_rate=0.70,
                location="Gotland EW Site"
            )
        ],
        context=OperationalContextAPI(
            location="Baltic Sea, near Gotland",
            weather="Low visibility, overcast",
            visibility_km=8,
            nato_air_policing_active=True,
            allied_aircraft_in_area=False,
            civilian_traffic_nearby=False,
            strategic_assets_nearby=["Gotland garrison", "Naval assets"],
            expected_follow_on_activity=False,
            historical_pattern="Russian intelligence flights monthly, usually maintain transponder"
        )
    )
    
    # Process scenario
    result = await process_c2_scenario(request)
    
    # Add analysis
    analysis = {
        "scenario": "Baltic Sea Air Defense",
        "sensor_count": 3,
        "sensor_sources": ["9LV (Naval)", "GBA C2 (Air Defense)", "BMS (Ground)"],
        "sensor_agreement": result.threat_summary.get('sensor_agreement', 0) * 100,
        "time_critical": result.threat_summary.get('time_to_boundary_min', 0) < 15,
        "nato_integration": "Active" if request.context.nato_air_policing_active else "Inactive",
        "key_challenge": "Multi-sensor fusion with contradictory data + NATO coordination"
    }
    
    return {
        **result.dict(),
        "validation_analysis": analysis
    }

# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                        SWEDISH C2 API SERVICE                                         ║
║                                                                                       ║
║  Starting FastAPI server on http://0.0.0.0:8002                                      ║
║  API Documentation: http://0.0.0.0:8002/docs                                         ║
║                                                                                       ║
║  Endpoints:                                                                           ║
║    POST /v1/c2              - Process multi-domain C2 scenario                       ║
║    POST /api/validate-baltic - Run Baltic Sea validation                             ║
║    GET  /api/templates       - List doctrine templates                               ║
║    GET  /api/system-types    - Get system types                                      ║
║                                                                                       ║
║  Integration:                                                                         ║
║    - 9LV Naval Combat Management System                                              ║
║    - GBA C2 Mobile Air Defense                                                       ║
║    - BMS Ground Surveillance                                                         ║
║    - NATO Air Policing Coordination                                                  ║
║                                                                                       ║
║  Requirements:                                                                        ║
║    - ARBITER service running on http://0.0.0.0:8000                                  ║
║    - swedish_c2_doctrine.py in same directory                                        ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "swedish_c2_api:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )
