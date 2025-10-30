#!/usr/bin/env python3
"""
SWEDISH C2 DOCTRINE SERVICE - INTEGRATED AIR DEFENSE
Multi-domain sensor fusion for Swedish Armed Forces

Integrates:
- 9LV Naval Combat Management System
- GBA C2 Mobile Air Defense
- BMS Ground Surveillance
- NATO Air Policing coordination

Created by: Joel Trout
For: Swedish Armed Forces / FOI validation
Version: 1.0
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

# ============================================================================
# ENUMS AND DATA CLASSES
# ============================================================================

class ThreatType(Enum):
    AIRCRAFT_TRANSPORT = "Transport Aircraft"
    AIRCRAFT_FIGHTER = "Fighter Aircraft"
    AIRCRAFT_RECONNAISSANCE = "Reconnaissance Aircraft"
    HELICOPTER = "Helicopter"
    CRUISE_MISSILE = "Cruise Missile"
    DRONE_MEDIUM = "Medium UAV"
    DRONE_SMALL = "Small UAV"
    UNKNOWN = "Unknown Contact"

class SystemType(Enum):
    # Swedish Systems
    GRIPEN_QRA = "JAS 39 Gripen QRA"
    GBA_C2_IRIS_T = "GBA C2 IRIS-T"
    GBA_C2_RBS_70 = "GBA C2 RBS 70"
    NAVAL_9LV = "9LV Naval System"
    
    # Portable systems
    RBS_70 = "RBS 70 MANPADS"
    
    # NATO integrated systems
    PATRIOT_BATTERY = "Patriot Battery (NATO)"
    
    # Electronic warfare
    ELECTRONIC_WARFARE = "Electronic Warfare System"

class ContactPriority(Enum):
    CRITICAL = "Critical"      # Sovereign airspace violation
    HIGH = "High"             # Approaching territorial boundary
    MEDIUM = "Medium"         # In international airspace, monitoring
    LOW = "Low"              # Distant, routine patrol

class SensorSource(Enum):
    NAVAL_9LV = "9LV"
    AIR_DEFENSE_GBA = "GBA_C2"
    GROUND_BMS = "BMS"
    NATO_AWE = "NATO_AWE"
    VISUAL_SOF = "Visual"

@dataclass
class SensorContact:
    """Single sensor contact"""
    source: SensorSource
    track_id: str
    bearing: int  # degrees
    range_nm: float
    altitude_m: int
    speed_knots: float
    confidence: float  # 0-1
    classification: str
    iff_response: Optional[str] = None
    data_age_seconds: int = 0
    ecm_detected: bool = False
    platform_name: Optional[str] = None

@dataclass
class MultiSensorThreat:
    """Correlated threat from multiple sensors"""
    contacts: List[SensorContact]
    threat_type: ThreatType
    priority: ContactPriority
    estimated_bearing: int
    estimated_range_nm: float
    time_to_boundary_minutes: float
    target_description: str
    
    def sensor_agreement(self) -> float:
        """Calculate how well sensors agree (0-1)"""
        if len(self.contacts) < 2:
            return 1.0
        
        bearings = [c.bearing for c in self.contacts]
        ranges = [c.range_nm for c in self.contacts]
        
        bearing_spread = max(bearings) - min(bearings)
        range_spread = max(ranges) - min(ranges)
        
        # Lower spread = higher agreement
        bearing_agreement = max(0, 1.0 - bearing_spread / 20.0)
        range_agreement = max(0, 1.0 - range_spread / 10.0)
        
        return (bearing_agreement + range_agreement) / 2

@dataclass
class AvailableAsset:
    """Available Swedish/NATO asset"""
    system_type: SystemType
    count: int
    ready_state: str  # "READY", "STANDBY_15MIN", "MAINTENANCE"
    effective_range_km: float
    response_time_minutes: int
    cost_per_engagement: int  # SEK
    success_rate: float
    location: str
    
    # NATO coordination
    requires_nato_clearance: bool = False
    requires_swedish_clearance: bool = True

@dataclass
class OperationalContext:
    """Swedish operational context"""
    location: str
    weather: str
    visibility_km: float
    nato_air_policing_active: bool
    allied_aircraft_in_area: bool
    civilian_traffic_nearby: bool
    strategic_assets_nearby: List[str]
    expected_follow_on_activity: bool
    historical_pattern: str

@dataclass
class GeneratedOption:
    """Single tactical option"""
    option_id: str
    title: str
    description: str
    template_id: str
    estimated_cost_sek: int
    estimated_success_rate: float
    assets_used: List[str]
    nato_coordination_required: bool
    swedish_sovereignty_maintained: bool

# ============================================================================
# SWEDISH DOCTRINE TEMPLATES
# ============================================================================

class SwedishAirDefenseDoctrine:
    """
    Swedish Integrated Air Defense Doctrine
    Post-NATO accession, maintains Swedish sovereignty
    """
    
    TEMPLATES = {
        'sovereign_qra_launch': {
            'title': 'Suverän QRA-start: Omedelbar visuell identifiering',
            'trigger': lambda t, a, c: (
                t.priority in [ContactPriority.CRITICAL, ContactPriority.HIGH] and
                t.time_to_boundary_minutes < 15 and
                any(asset.system_type == SystemType.GRIPEN_QRA for asset in a)
            ),
            'template': """
ALTERNATIV: Suverän svensk QRA-start för visuell identifiering

SVENSK DOKTRIN: Vid okända flygplan närmande svenskt luftrum → QRA-start OMEDELBART

LUFTLÄGE:
- Kontakt: {contact_description}
- Avstånd: {range}nm från svensk gräns
- Tid till territorialgräns: {time_to_boundary} minuter
- QRA beredskapstid: {qra_response_time} minuter
- Sensorer: {sensor_summary}

ÅTGÄRD:
- {qra_count}x JAS 39 Gripen från {qra_base}
- Uppgift: Visuell identifiering FÖRE territorialgräns
- Beredskapsnivå: {scramble_time} minuter
- Beredskap: {backup_systems}

NATO-KOORDINATION:
- {nato_status}
- Svenska

 Gripen behåller nationell kommando
- Parallell information till NATO CAOC

SUVERÄNITET:
✓ Svensk kontroll över eget luftrum
✓ Nationell kommandokedja bibehållen
✓ NATO informerad enligt avtal
✓ Visuell ID före territorialgräns

KOSTNAD: {cost:,} SEK
FRAMGÅNGSSANNOLIKHET: {success_rate}%
SUVERÄNITET: BIBEHÅLLEN
"""
        },
        
        'multi_sensor_correlation': {
            'title': 'Avvakta: Multidomän-sensorfusion pågår',
            'trigger': lambda t, a, c: (
                t.sensor_agreement() < 0.7 and
                t.time_to_boundary_minutes > 10 and
                t.priority != ContactPriority.CRITICAL
            ),
            'template': """
ALTERNATIV: Fortsatt multisensor-spårning, avvakta ytterligare data

SENSORLÄGE:
- {sensor_count} sensorer detekterar kontakt
- Sensoröverensstämmelse: {agreement_percent}% (LÅG)
- Motsägande data:
  - 9LV: Bäring {bearing_9lv}°, avstånd {range_9lv}nm
  - GBA C2: Bäring {bearing_gba}°, avstånd {range_gba}nm
  - BMS: Bäring {bearing_bms}°, avstånd {range_bms}nm

TIDSANALYS:
- Tid till gräns: {time_to_boundary} minuter
- QRA beredskapstid: {qra_time} minuter
- Marginal: {time_margin} minuter för fortsatt spårning

ÅTGÄRD:
- Fortsätt multisensor-spårning i {track_time} minuter
- Korrelera data från alla tre system
- Begär NATO AWE-bekräftelse om tillgängligt
- QRA bibehålls på {readiness_level}

FÖRDELAR:
- Undviker onödig QRA-start vid motstridiga data
- {cost_avoided:,} SEK sparade om falsklarm
- Bättre situationsmedvetenhet före beslut
- Tid för NATO-koordination

RISKER:
- Om verkligt hot: {risk_minutes} minuters förlorad tid
- Måste vara redo att starta QRA omedelbart vid förstärkt hot

KOSTNAD: 0 SEK (fortsatt spårning)
FRAMGÅNGSSANNOLIKHET: {success_rate}%
TIDSMARGINAL: {time_margin} minuter
"""
        },
        
        'layered_defense_baltic': {
            'title': 'Flerlagers försvar: 9LV + GBA C2 + QRA',
            'trigger': lambda t, a, c: (
                t.priority == ContactPriority.HIGH and
                any(a.system_type == SystemType.NAVAL_9LV for a in a) and
                any(a.system_type == SystemType.GBA_C2_IRIS_T for a in a)
            ),
            'template': """
ALTERNATIV: Flerlagers integrerat försvar (9LV + GBA C2 + QRA)

DOKTRIN: Högt prioriterat hot → använd alla tillgängliga lager

LAGER 1 (Avstånd >30km): HMS {naval_platform} 9LV
- {naval_missiles}x sjömålsrobot tillgängliga
- Effektivt avstånd: {naval_range}km
- Kostnad: {naval_cost:,} SEK per robot
- Framgång: {naval_success}%

LAGER 2 (Avstånd 15-30km): GBA C2 Mobil luftvärn
- {gba_missiles}x IRIS-T eller RBS 70
- Placering: {gba_location}
- Kostnad: {gba_cost:,} SEK per robot
- Framgång: {gba_success}%

LAGER 3 (Visuell ID): JAS 39 Gripen QRA
- {qra_aircraft}x Gripen från {qra_base}
- Visuell identifiering och eskort
- Starttid: {qra_time} minuter
- Kostnad: {qra_cost:,} SEK

INTEGRATION:
- Alla system delar måldata via TARAS
- 9LV ger tidig varning och första skott
- GBA C2 täcker medeldistans
- QRA ger visuell bekräftelse och diplomati

EKONOMI:
- Minsta kostnad: {min_cost:,} SEK (endast 9LV lyckas)
- Typisk kostnad: {typical_cost:,} SEK (9LV + GBA C2)
- Maximal kostnad: {max_cost:,} SEK (alla lager)

KUMULATIV FRAMGÅNG: {cumulative_success}%

KOSTNAD: {cost:,} SEK (förväntat)
FRAMGÅNG: {cumulative_success}%
LAGER: 3 (9LV + GBA C2 + QRA)
"""
        },
        
        'nato_coordinated_response': {
            'title': 'NATO-koordinerat svar: Alliansintegration',
            'trigger': lambda t, a, c: (
                c.nato_air_policing_active and
                t.time_to_boundary_minutes > 8 and
                any(a.requires_nato_clearance for a in a)
            ),
            'template': """
ALTERNATIV: NATO-koordinerad respons med svensk suveränitetskontroll

NATO-LÄGE:
- NATO Air Policing: AKTIV
- {nato_assets} tillgängliga i regionen
- CAOC Uedem koordinerar
- Svensk nationell kommando bibehålls

SVENSK INSATS:
- {swedish_primary}x {swedish_system}
- Nationell kommandokedja
- Parallell NATO-kommunikation
- Kostnad: {swedish_cost:,} SEK

NATO-STÖD:
- {nato_support_description}
- Responsdistans: {nato_response_time} minuter
- Kostnad för Sverige: 0 SEK (NATO-stöd)

KOORDINATION:
- Svensk insats startar OMEDELBART
- NATO informeras parallellt
- Allians ger tilläggsstöd om begärt
- Svenska Gripen bibehåller primär ansvar

FÖRDELAR:
- Demonstrerar NATO-integration
- Svensk suveränitet bibehållen
- Alliansresurser tillgängliga
- Delad situationsmedvetenhet

SUVERÄNITET:
✓ Sverige behåller slutgiltigt beslut
✓ Nationell kommando över svenska enheter
✓ NATO som stöd, inte primär aktör
✓ Uppfyller alliansförpliktelser

KOSTNAD: {cost:,} SEK (endast svensk insats)
NATO-STÖD: Tillgängligt om begärt
SUVERÄNITET: BIBEHÅLLEN
"""
        },
        
        'minimal_response_routine': {
            'title': 'Minimal respons: Rutinmässig övervakning',
            'trigger': lambda t, a, c: (
                t.priority == ContactPriority.LOW and
                t.range_nm > 50 and
                c.historical_pattern == "Routine Russian patrol"
            ),
            'template': """
ALTERNATIV: Minimal respons - fortsatt övervakning

BEDÖMNING:
- Kontakt: {contact_description}
- Avstånd: {range}nm (långt från gräns)
- Historiskt mönster: {historical_pattern}
- Prioritet: LÅG

ÅTGÄRD:
- Fortsätt passiv spårning med alla sensorer
- INGEN QRA-start
- Bibehåll normal beredskapsnivå
- Dokumentera för mönsteranalys

SPARA RESURSER:
- QRA-start undviks: {qra_cost:,} SEK sparat
- Flygbränsle sparat
- Piloter bibehålls på beredskap för kritiska händelser
- Normal vardagsrörelse av ryska flygplan

RISKVÄRDERING:
- Acceptabel: Långt från svenskt luftrum
- Mönster: Rutinmässig patrull (händer månadsvis)
- Tid för eskalering: >30 minuter varning vid kursändring

ESKALERINGSPLAN:
- VID kursändring mot svenskt luftrum → aktivera QRA
- VID onormalt beteende → höj beredskap
- Kontinuerlig övervakning bibehålls

KOSTNAD: 0 SEK
RISK: ACCEPTABEL
ÅTGÄRD: Passiv övervakning
"""
        },
        
        'electronic_warfare_priority': {
            'title': 'Elektronisk krigföring: EW-första approach',
            'trigger': lambda t, a, c: (
                t.threat_type in [ThreatType.DRONE_SMALL, ThreatType.DRONE_MEDIUM] and
                any(a.system_type == SystemType.ELECTRONIC_WARFARE for a in a)
            ),
            'template': """
ALTERNATIV: Elektronisk krigföring före kinetiskt svar

HOTTYP: {threat_type} - Sårbar för EW

LAGER 1: Elektronisk motverkan
- EW-system aktivt
- GPS/GLONASS-störning
- Kommunikationsstörning
- Kostnad: 0 SEK (återanvändbar förmåga)
- Framgång mot drönare: {ew_success}%

LAGER 2: Kinetiskt (vid EW-miss)
- {kinetic_system} beredskap
- Aktiveras endast om EW misslyckas
- Kostnad: {kinetic_cost:,} SEK
- Framgång: {kinetic_success}%

SÄRSKILT FÖR DRÖNARE:
- Högt beroende av GPS-navigering
- Kommunikation kritisk för kontroll
- EW mycket effektivt mot kommersiella drönare
- Ingen robotkostnad vid EW-framgång

EKONOMI:
- EW-framgång: 0 SEK
- EW-miss, kinetic fallback: {kinetic_cost:,} SEK
- Förväntad kostnad: {expected_cost:,} SEK

KUMULATIV FRAMGÅNG: {cumulative_success}%

KOSTNAD: {expected_cost:,} SEK (förväntat)
FRAMGÅNG: {cumulative_success}%
METOD: EW-först, kinetisk backup
"""
        }
    }
    
    @staticmethod
    def generate_options(threat: MultiSensorThreat,
                        assets: List[AvailableAsset],
                        context: OperationalContext) -> List[GeneratedOption]:
        """Generate tactical options from Swedish doctrine"""
        
        options = []
        
        for template_id, template_def in SwedishAirDefenseDoctrine.TEMPLATES.items():
            # Check trigger
            if not template_def['trigger'](threat, assets, context):
                continue
            
            # Calculate parameters
            params = SwedishAirDefenseDoctrine._calculate_parameters(
                template_id, threat, assets, context
            )
            
            if params is None:
                continue
            
            # Fill template
            description = template_def['template'].format(**params)
            
            options.append(GeneratedOption(
                option_id=f"SWEDISH_C2_{template_id}_{int(time.time())}",
                title=template_def['title'],
                description=description.strip(),
                template_id=template_id,
                estimated_cost_sek=params.get('cost', 0),
                estimated_success_rate=params.get('success_rate', 80.0),
                assets_used=params.get('assets_used', []),
                nato_coordination_required=params.get('nato_required', False),
                swedish_sovereignty_maintained=params.get('sovereignty', True)
            ))
        
        return options
    
    @staticmethod
    def _calculate_parameters(template_id: str,
                             threat: MultiSensorThreat,
                             assets: List[AvailableAsset],
                             context: OperationalContext) -> Optional[Dict]:
        """Calculate parameters for template"""
        
        # Find available systems
        qra = [a for a in assets if a.system_type == SystemType.GRIPEN_QRA]
        naval = [a for a in assets if a.system_type == SystemType.NAVAL_9LV]
        gba = [a for a in assets if "GBA" in a.system_type.value]
        ew = [a for a in assets if a.system_type == SystemType.ELECTRONIC_WARFARE]
        
        if template_id == 'sovereign_qra_launch':
            if not qra:
                return None
            
            qra_asset = qra[0]
            
            # Sensor summary
            sensor_summary = f"{len(threat.contacts)} sensorer ({', '.join(c.source.value for c in threat.contacts)})"
            
            return {
                'contact_description': f"{threat.estimated_range_nm:.1f}nm, bäring {threat.estimated_bearing}°",
                'range': threat.estimated_range_nm,
                'time_to_boundary': threat.time_to_boundary_minutes,
                'qra_response_time': qra_asset.response_time_minutes,
                'sensor_summary': sensor_summary,
                'qra_count': qra_asset.count,
                'qra_base': qra_asset.location,
                'scramble_time': qra_asset.response_time_minutes,
                'backup_systems': ', '.join(a.system_type.value for a in (naval + gba)[:2]),
                'nato_status': "NATO CAOC Uedem informeras parallellt" if context.nato_air_policing_active else "Nationell operation",
                'cost': qra_asset.cost_per_engagement,
                'success_rate': int(qra_asset.success_rate * 100),
                'assets_used': [qra_asset.system_type.value],
                'nato_required': False,
                'sovereignty': True
            }
        
        elif template_id == 'multi_sensor_correlation':
            # Calculate sensor disagreement
            agreement = threat.sensor_agreement()
            
            contacts_by_source = {c.source.value: c for c in threat.contacts}
            
            time_margin = threat.time_to_boundary_minutes - (qra[0].response_time_minutes if qra else 15)
            
            # Safe sensor data extraction with fallbacks
            bearing_9lv = contacts_by_source['9LV'].bearing if '9LV' in contacts_by_source else 'N/A'
            range_9lv = contacts_by_source['9LV'].range_nm if '9LV' in contacts_by_source else 0

            bearing_gba = contacts_by_source['GBA_C2'].bearing if 'GBA_C2' in contacts_by_source else (threat.contacts[1].bearing if len(threat.contacts) > 1 else threat.contacts[0].bearing)
            range_gba = contacts_by_source['GBA_C2'].range_nm if 'GBA_C2' in contacts_by_source else (threat.contacts[1].range_nm if len(threat.contacts) > 1 else threat.contacts[0].range_nm)

            bearing_bms = contacts_by_source['BMS'].bearing if 'BMS' in contacts_by_source else threat.contacts[-1].bearing
            range_bms = contacts_by_source['BMS'].range_nm if 'BMS' in contacts_by_source else threat.contacts[-1].range_nm

            return {
                'sensor_count': len(threat.contacts),
                'agreement_percent': int(agreement * 100),
                'bearing_9lv': bearing_9lv,
                'range_9lv': range_9lv,
                'bearing_gba': bearing_gba,
                'range_gba': range_gba,
                'bearing_bms': bearing_bms,
                'range_bms': range_bms,
                'time_to_boundary': threat.time_to_boundary_minutes,
                'qra_time': qra[0].response_time_minutes if qra else 15,
                'time_margin': max(0, time_margin),
                'track_time': min(5, time_margin // 2) if time_margin > 0 else 0,
                'readiness_level': "15-minuters beredskap" if time_margin > 15 else "5-minuters beredskap",
                'cost_avoided': qra[0].cost_per_engagement if qra else 200000,
                'risk_minutes': min(5, time_margin // 2) if time_margin > 0 else 0,
                'cost': 0,
                'success_rate': 85,
                'assets_used': ['Multisensor tracking'],
                'nato_required': False,
                'sovereignty': True
            }
        
        elif template_id == 'layered_defense_baltic':
            if not naval or not gba or not qra:
                return None
            
            naval_asset = naval[0]
            gba_asset = gba[0]
            qra_asset = qra[0]
            
            naval_success = 0.85
            gba_success = 0.90
            qra_success = 0.95
            
            # Cumulative: 1 - (all fail)
            cumulative = 1 - (1 - naval_success) * (1 - gba_success) * (1 - qra_success)
            
            naval_cost = naval_asset.cost_per_engagement
            gba_cost = gba_asset.cost_per_engagement  
            qra_cost = qra_asset.cost_per_engagement
            
            return {
                'naval_platform': naval_asset.location.split()[-1] if naval_asset.location else "Karlstad",
                'naval_missiles': naval_asset.count,
                'naval_range': naval_asset.effective_range_km,
                'naval_cost': naval_cost,
                'naval_success': int(naval_success * 100),
                'gba_missiles': gba_asset.count,
                'gba_location': gba_asset.location,
                'gba_cost': gba_cost,
                'gba_success': int(gba_success * 100),
                'qra_aircraft': qra_asset.count,
                'qra_base': qra_asset.location,
                'qra_time': qra_asset.response_time_minutes,
                'qra_cost': qra_cost,
                'min_cost': naval_cost,
                'typical_cost': naval_cost + gba_cost,
                'max_cost': naval_cost + gba_cost + qra_cost,
                'cumulative_success': int(cumulative * 100),
                'cost': naval_cost + gba_cost,  # Expected: first 2 layers
                'success_rate': int(cumulative * 100),
                'assets_used': [naval_asset.system_type.value, gba_asset.system_type.value, qra_asset.system_type.value],
                'nato_required': False,
                'sovereignty': True
            }
        
        elif template_id == 'nato_coordinated_response':
            if not qra:
                return None
            
            qra_asset = qra[0]
            
            return {
                'nato_assets': "F-16 CAP (Polish), AWE (German)" if context.nato_air_policing_active else "None active",
                'swedish_primary': qra_asset.count,
                'swedish_system': qra_asset.system_type.value,
                'swedish_cost': qra_asset.cost_per_engagement,
                'nato_support_description': "F-16 escort available, AWE correlation available" if context.nato_air_policing_active else "No NATO assets currently available",
                'nato_response_time': 8 if context.nato_air_policing_active else 20,
                'cost': qra_asset.cost_per_engagement,
                'success_rate': 90,
                'assets_used': [qra_asset.system_type.value, "NATO coordination"],
                'nato_required': True,
                'sovereignty': True
            }
        
        elif template_id == 'minimal_response_routine':
            return {
                'contact_description': f"{threat.threat_type.value}, bäring {threat.estimated_bearing}°",
                'range': threat.estimated_range_nm,
                'historical_pattern': context.historical_pattern,
                'qra_cost': qra[0].cost_per_engagement if qra else 200000,
                'cost': 0,
                'success_rate': 0,  # No action taken
                'assets_used': ['Passive tracking'],
                'nato_required': False,
                'sovereignty': True
            }
        
        elif template_id == 'electronic_warfare_priority':
            if not ew:
                return None
            
            ew_asset = ew[0]
            
            kinetic_asset = gba[0] if gba else naval[0] if naval else None
            if not kinetic_asset:
                return None
            
            ew_success = 0.70
            kinetic_success = 0.85
            cumulative = 1 - (1 - ew_success) * (1 - kinetic_success)
            
            kinetic_cost = kinetic_asset.cost_per_engagement
            expected_cost = kinetic_cost * (1 - ew_success)  # Only pay if EW fails
            
            return {
                'threat_type': threat.threat_type.value,
                'ew_success': int(ew_success * 100),
                'kinetic_system': kinetic_asset.system_type.value,
                'kinetic_cost': kinetic_cost,
                'kinetic_success': int(kinetic_success * 100),
                'expected_cost': int(expected_cost),
                'cumulative_success': int(cumulative * 100),
                'cost': int(expected_cost),
                'success_rate': int(cumulative * 100),
                'assets_used': [ew_asset.system_type.value, kinetic_asset.system_type.value],
                'nato_required': False,
                'sovereignty': True
            }
        
        return None

# ============================================================================
# ARBITER INTEGRATION
# ============================================================================
class SwedishC2Service:
    """Main C2 service: Generate options + ARBITER evaluation"""
    
    def __init__(self, arbiter_url: str = "https://api.arbiter.traut.ai/v1/compare"):
        self.arbiter_url = arbiter_url
    
    def process_multi_sensor_scenario(self,
                                      threat: MultiSensorThreat,
                                      assets: List[AvailableAsset],
                                      context: OperationalContext) -> Dict:
        """
        Process multi-sensor C2 scenario:
        1. Generate options from Swedish doctrine
        2. Evaluate with ARBITER
        3. Return ranked recommendations
        """
        
        print(f"\n{'='*80}")
        print(f"SWEDISH C2 DOCTRINE SERVICE - Multi-Domain Integration")
        print(f"{'='*80}\n")
        
        # Generate options
        print(f"⚙️  Generating tactical options from Swedish doctrine...")
        start = time.time()
        
        options = SwedishAirDefenseDoctrine.generate_options(threat, assets, context)
        
        gen_time = time.time() - start
        print(f"✓ Generated {len(options)} options in {gen_time*1000:.0f}ms\n")
        
        for i, opt in enumerate(options, 1):
            print(f"{i}. {opt.title}")
            print(f"   Template: {opt.template_id}")
            print(f"   Cost: {opt.estimated_cost_sek:,} SEK, Success: {opt.estimated_success_rate:.0f}%")
            print(f"   Assets: {', '.join(opt.assets_used)}\n")
        
        # Build ARBITER query
        query = self._build_c2_query(threat, assets, context)
        candidates = [opt.description for opt in options]
        
        # Query ARBITER
        print(f"⚡ Querying ARBITER for coherence evaluation...")
        arbiter_result = self._query_arbiter(query, candidates)
        
        if not arbiter_result['success']:
            return {
                'success': False,
                'error': arbiter_result.get('error'),
                'generated_options': options
            }
        
        # Combine results
        ranked = self._combine_results(options, arbiter_result['result'])
        
        return {
            'success': True,
            'generation_time_ms': gen_time * 1000,
            'arbiter_latency_ms': arbiter_result['latency'] * 1000,
            'total_time_ms': (gen_time + arbiter_result['latency']) * 1000,
            'options_generated': len(options),
            'ranked_recommendations': ranked,
            'query': query,
            'threat_summary': {
                'type': threat.threat_type.value,
                'priority': threat.priority.value,
                'range_nm': threat.estimated_range_nm,
                'time_to_boundary_min': threat.time_to_boundary_minutes,
                'sensor_agreement': threat.sensor_agreement()
            }
        }
    
    def _build_c2_query(self, threat: MultiSensorThreat,
                       assets: List[AvailableAsset],
                       context: OperationalContext) -> str:
        """Build semantic query for Swedish C2"""
        
        query = f"""
Jag är svensk luftvärnskoordinator för {context.location} sektorn.

MULTIDOMÄN-SENSORINFORMATION:
"""
        
        for contact in threat.contacts:
            query += f"""
[{contact.source.value}] {contact.platform_name or contact.source.value}:
- Spår: {contact.track_id}
- Bäring: {contact.bearing}°, Avstånd: {contact.range_nm}nm
- Höjd: {contact.altitude_m}m, Hastighet: {contact.speed_knots}kts
- Klassificering: {contact.classification}
- Tillförlitlighet: {int(contact.confidence * 100)}%
- Dataålder: {contact.data_age_seconds}s
"""
            if contact.iff_response:
                query += f"• IFF: {contact.iff_response}\n"
            if contact.ecm_detected:
                query += f"• EW-aktivitet detekterad\n"
        
        query += f"""
SENSORÖVERENSSTÄMMELSE: {int(threat.sensor_agreement() * 100)}%

TILLGÄNGLIGA SYSTEM:
"""
        
        for asset in assets:
            query += f"""
- {asset.system_type.value}: {asset.count} enheter
  - Beredskap: {asset.ready_state}
  - Effektivt avstånd: {asset.effective_range_km}km
  - Insatstid: {asset.response_time_minutes} minuter
  - Placering: {asset.location}
"""
        
        query += f"""
OPERATIVT LÄGE:
- Väder: {context.weather}, Sikt: {context.visibility_km}km
- NATO Air Policing: {'AKTIV' if context.nato_air_policing_active else 'EJ AKTIV'}
- Allierade flygplan i området: {'JA' if context.allied_aircraft_in_area else 'NEJ'}
- Civiltrafik närliggande: {'JA' if context.civilian_traffic_nearby else 'NEJ'}
- Strategiska tillgångar: {', '.join(context.strategic_assets_nearby) if context.strategic_assets_nearby else 'Inga'}

TID TILL TERRITORIALGRÄNS: {threat.time_to_boundary_minutes:.1f} minuter
PRIORITET: {threat.priority.value}
HISTORISKT MÖNSTER: {context.historical_pattern}

Behöver TAKTISK REKOMMENDATION enligt svensk doktrin med NATO-integration.
"""
        
        return query.strip()
    
    def _query_arbiter(self, query: str, candidates: List[str]) -> Dict:
        """Query ARBITER API"""
        try:
            start = time.time()
            
            response = requests.post(
                self.arbiter_url,
                json={
                    "query": query,
                    "candidates": candidates
                },
                timeout=30
            )
            
            latency = time.time() - start
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'result': response.json(),
                    'latency': latency
                }
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}",
                    'latency': latency
                }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'latency': 0
            }
    
    def _combine_results(self, options: List[GeneratedOption],
                        arbiter_result: Dict) -> List[Dict]:
        """Combine options with ARBITER rankings"""
        
        ranked = []
        
        for i, arb_option in enumerate(arbiter_result['top'], 1):
            matching = None
            for opt in options:
                if opt.description == arb_option['text']:
                    matching = opt
                    break
            
            ranked.append({
                'rank': i,
                'coherence': arb_option['score'],
                'title': matching.title if matching else f"Option {i}",
                'description': arb_option['text'],
                'template_id': matching.template_id if matching else 'unknown',
                'estimated_cost_sek': matching.estimated_cost_sek if matching else 0,
                'estimated_success_rate': matching.estimated_success_rate if matching else 0,
                'assets_used': matching.assets_used if matching else [],
                'nato_coordination': matching.nato_coordination_required if matching else False,
                'swedish_sovereignty': matching.swedish_sovereignty_maintained if matching else True,
                'recommendation_level': 'HIGH' if arb_option['score'] > 0.80 else 'MEDIUM' if arb_option['score'] > 0.70 else 'LOW'
            })
        
        return ranked

# ============================================================================
# VALIDATION SCENARIO - BALTIC SEA AIR DEFENSE
# ============================================================================

def validate_baltic_sea_scenario():
    """Validation: Baltic Sea unidentified aircraft"""
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║                  SWEDISH C2 VALIDATION - BALTIC SEA AIR DEFENSE                      ║
║                                                                                       ║
║  Scenario: Unidentified aircraft approaching Gotland                                 ║
║  Multiple sensor sources with contradictory data                                     ║
║  Testing: Swedish doctrine + NATO coordination                                       ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Multi-sensor contacts
    contacts = [
        SensorContact(
            source=SensorSource.NAVAL_9LV,
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
        SensorContact(
            source=SensorSource.AIR_DEFENSE_GBA,
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
        SensorContact(
            source=SensorSource.GROUND_BMS,
            track_id="TRACK-GOLF-7",
            bearing=98,
            range_nm=89,
            altitude_m=8800,
            speed_knots=410,
            confidence=0.72,
            classification="No IFF response, evasive pattern",
            data_age_seconds=180
        )
    ]
    
    threat = MultiSensorThreat(
        contacts=contacts,
        threat_type=ThreatType.AIRCRAFT_TRANSPORT,
        priority=ContactPriority.HIGH,
        estimated_bearing=95,
        estimated_range_nm=87,
        time_to_boundary_minutes=12.0,
        target_description="Okänt flygplan närmar sig svenskt luftrum från öst"
    )
    
    # Available assets
    assets = [
        AvailableAsset(
            system_type=SystemType.GRIPEN_QRA,
            count=2,
            ready_state="STANDBY_15MIN",
            effective_range_km=800,
            response_time_minutes=15,
            cost_per_engagement=200000,
            success_rate=0.95,
            location="F17 Ronneby",
            requires_nato_clearance=False
        ),
        AvailableAsset(
            system_type=SystemType.GBA_C2_IRIS_T,
            count=4,
            ready_state="READY",
            effective_range_km=40,
            response_time_minutes=2,
            cost_per_engagement=500000,
            success_rate=0.93,
            location="Gotland",
            requires_nato_clearance=False
        ),
        AvailableAsset(
            system_type=SystemType.NAVAL_9LV,
            count=2,
            ready_state="READY",
            effective_range_km=160,
            response_time_minutes=1,
            cost_per_engagement=1000000,
            success_rate=0.90,
            location="HMS Karlstad",
            requires_nato_clearance=False
        ),
        AvailableAsset(
            system_type=SystemType.ELECTRONIC_WARFARE,
            count=1,
            ready_state="READY",
            effective_range_km=50,
            response_time_minutes=0,
            cost_per_engagement=0,
            success_rate=0.70,
            location="Gotland EW Site"
        )
    ]
    
    # Context
    context = OperationalContext(
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
    
    # Process
    service = SwedishC2Service()
    
    result = service.process_multi_sensor_scenario(
        threat=threat,
        assets=assets,
        context=context
    )
    
    # Display
    if result['success']:
        print(f"\n{'='*80}")
        print(f"SWEDISH C2 RECOMMENDATIONS")
        print(f"{'='*80}\n")
        
        print(f"⏱️  Performance:")
        print(f"   Total time: {result['total_time_ms']:.0f}ms")
        print(f"   Sensor agreement: {result['threat_summary']['sensor_agreement']*100:.0f}%\n")
        
        print(f"📊 Top 3 Recommendations:\n")
        
        for rec in result['ranked_recommendations'][:3]:
            print(f"{'='*80}")
            print(f"#{rec['rank']} | Coherence: {rec['coherence']:.4f} | {rec['recommendation_level']}")
            print(f"{rec['title']}")
            print(f"Cost: {rec['estimated_cost_sek']:,} SEK")
            print(f"Success: {rec['estimated_success_rate']}%")
            print(f"Assets: {', '.join(rec['assets_used'])}")
            print(f"NATO Coordination: {'Required' if rec['nato_coordination'] else 'Not required'}")
            print(f"Swedish Sovereignty: {'✓ Maintained' if rec['swedish_sovereignty'] else '✗ Compromised'}")
            print()
        
        print(f"✅ Swedish C2 validation complete")
    
    else:
        print(f"\n❌ Error: {result.get('error')}")

if __name__ == "__main__":
    validate_baltic_sea_scenario()
