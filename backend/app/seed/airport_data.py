"""Platform-owned master data: screens, outlets, advertisers, campaigns,
creatives, promo codes, learning defaults and 30-day synthetic history.

All fictional (MQI world). Fields the AODB/AIDX/ACRIS sources do not define are
platform data and never presented as external-standard fields (AGENTS §5).
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

BRAND_BG = "#0f172a"


def build_screens(zones: list[dict], target: int = 180) -> dict:
    """180 screens: a portrait gate screen per gate, 4 concourse long-range
    (LWIDE) panels per gate concourse, 3 inline digitals per concourse and
    corridor totes in retail/security zones; deterministic order."""
    screens: dict[str, dict] = {}
    seq = 1
    for z in zones:
        if z["kind"] == "gate" and z["gates"]:
            for _i, g in enumerate(z["gates"]):
                screens[f"scr-{seq:03d}"] = dict(
                    id=f"scr-{seq:03d}", terminal=z["terminal"], concourse=z["concourse"],
                    zone_id=z["id"], zone=z["name"], gate=g, nearest_gates=z["gates"][:3],
                    kind="gate", width_px=1080, height_px=1920, online=True, degraded=False,
                )
                seq += 1
            for j in range(4):
                g = z["gates"][min(j * (len(z["gates"]) // 4 + 1), len(z["gates"]) - 1)]
                screens[f"scr-{seq:03d}"] = dict(
                    id=f"scr-{seq:03d}", terminal=z["terminal"], concourse=z["concourse"],
                    zone_id=z["id"], zone=z["name"], gate=g, nearest_gates=z["gates"][:2],
                    kind="wide", width_px=1920, height_px=1080, online=True, degraded=False,
                )
                seq += 1
            for _j in range(3):
                g = z["gates"][min(_j * (len(z["gates"]) // 3 + 1), len(z["gates"]) - 1)]
                screens[f"scr-{seq:03d}"] = dict(
                    id=f"scr-{seq:03d}", terminal=z["terminal"], concourse=z["concourse"],
                    zone_id=z["id"], zone=z["name"], gate=g, nearest_gates=z["gates"][:2],
                    kind="digital", width_px=1920, height_px=1080, online=True, degraded=False,
                )
                seq += 1
        elif z["kind"] in ("retail", "security"):
            k = "tote" if z["kind"] == "retail" else "digital"
            for _j in range(4):
                screens[f"scr-{seq:03d}"] = dict(
                    id=f"scr-{seq:03d}", terminal=z["terminal"], concourse=z["concourse"],
                    zone_id=z["id"], zone=z["name"], gate=None, nearest_gates=z["gates"][:2],
                    kind=k, width_px=1080, height_px=1920, online=True, degraded=False,
                )
                seq += 1
    # fill to target with retail-corridor totes
    retail = [z for z in zones if z["kind"] == "retail"] or zones
    r = 0
    while seq <= target:
        z = retail[r % len(retail)]
        screens[f"scr-{seq:03d}"] = dict(
            id=f"scr-{seq:03d}", terminal=z["terminal"], concourse=z["concourse"],
            zone_id=z["id"], zone=z["name"], gate=None, nearest_gates=z["gates"][:2],
            kind="tote", width_px=1080, height_px=1920, online=True, degraded=False,
        )
        seq += 1
        r += 1
    return screens


TERMS = ("T1", "T2")


def build_outlets() -> dict:
    outlets: dict[str, dict] = {}
    zid1, zid2 = "T1-retail-main", "T2-retail-main"
    outlets["out-t1-coffee"] = dict(id="out-t1-coffee", name="Harbour Roasters Coffee kiosk", terminal="T1", zone_id=zid1, zone="T1 Retail corridor", kind="coffee", advertiser_id="adv-harbour-roasters", dwell_focus=True)
    outlets["out-t1-deli"] = dict(id="out-t1-deli", name="Meridian Deli T1", terminal="T1", zone_id=zid1, zone="T1 Retail corridor", kind="fnb", advertiser_id="adv-meridiandeli", dwell_focus=True)
    outlets["out-t1-books"] = dict(id="out-t1-books", name="Skyline Books T1", terminal="T1", zone_id=zid1, zone="T1 Retail corridor", kind="retail", advertiser_id="adv-skyline", dwell_focus=False)
    outlets["out-t1-apparel"] = dict(id="out-t1-apparel", name="Aerowear T1", terminal="T1", zone_id=zid1, zone="T1 Retail corridor", kind="retail", advertiser_id="adv-aerowear", dwell_focus=False)
    outlets["out-t1-toys"] = dict(id="out-t1-toys", name="Sprockets Toy Cellar T1", terminal="T1", zone_id=zid1, zone="T1 Retail corridor", kind="toys", advertiser_id="adv-sprockets", dwell_focus=False)
    outlets["out-t1-candy"] = dict(id="out-t1-candy", name="Sugarbird Sweets T1", terminal="T1", zone_id=zid1, zone="T1 Retail corridor", kind="retail", advertiser_id="adv-sugarbird", dwell_focus=False)
    outlets["out-t1-pharma"] = dict(id="out-t1-pharma", name="Travel Health Hub T1", terminal="T1", zone_id=zid1, zone="T1 Retail corridor", kind="services", advertiser_id="adv-healthhub", dwell_focus=True)
    outlets["out-t1-timew"] = dict(id="out-t1-timew", name="Vista Watches T1", terminal="T1", zone_id=zid1, zone="T1 Retail corridor", kind="retail", advertiser_id="adv-vista", dwell_focus=False)
    outlets["out-t1-luggage"] = dict(id="out-t1-luggage", name="MeridBaggage service point", terminal="T1", zone_id=zid1, zone="T1 Retail corridor", kind="services", advertiser_id="adv-meridian-retail", dwell_focus=False)
    outlets["out-t1-snack"] = dict(id="out-t1-snack", name="North Pitch Coffee T1", terminal="T1", zone_id=zid1, zone="T1 Retail corridor", kind="coffee", advertiser_id="adv-harbour-roasters", dwell_focus=True)
    # T2
    outlets["out-t2-df-perfume"] = dict(id="out-t2-df-perfume", name="Meridian Aromatics (duty-free)", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="duty-free", advertiser_id="adv-aromatics", dwell_focus=True)
    outlets["out-t2-df-liquor"] = dict(id="out-t2-df-liquor", name="Harbour Cellars (duty-free)", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="duty-free", advertiser_id="adv-cellars", dwell_focus=True)
    outlets["out-t2-candy"] = dict(id="out-t2-candy", name="Sugarbird duty-free confectionery", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="retail", advertiser_id="adv-sugarbird", dwell_focus=False)
    outlets["out-t2-toys"] = dict(id="out-t2-toys", name="Sprockets Toy Cellar T2", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="toys", advertiser_id="adv-sprockets", dwell_focus=False)
    outlets["out-t2-apparel"] = dict(id="out-t2-apparel", name="Aerowear international", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="retail", advertiser_id="adv-aerowear", dwell_focus=False)
    outlets["out-t2-watches"] = dict(id="out-t2-watches", name="Vista Watch & Jewels intl", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="retail", advertiser_id="adv-vista", dwell_focus=False)
    outlets["out-t2-cosmetics"] = dict(id="out-t2-cosmetics", name="Belle Vida cosmetics T2", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="retail", advertiser_id="adv-aromatics", dwell_focus=False)
    outlets["out-t2-sunwear"] = dict(id="out-t2-sunwear", name="Sunwear Co beach shop", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="retail", advertiser_id="adv-sunwear", dwell_focus=False)
    outlets["out-t2-coffee"] = dict(id="out-t2-coffee", name="Harbour Roasters international", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="coffee", advertiser_id="adv-harbour-roasters", dwell_focus=True)
    outlets["out-t2-sushi"] = dict(id="out-t2-sushi", name="Sushi Bay Meridian", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="fnb", advertiser_id="adv-sushibay", dwell_focus=True)
    outlets["out-t2-pizza"] = dict(id="out-t2-pizza", name="MeroStone pizza bar", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="fnb", advertiser_id="adv-meridiandeli", dwell_focus=True)
    outlets["out-t2-books"] = dict(id="out-t2-books", name="Skyline Books intl", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="retail", advertiser_id="adv-skyline", dwell_focus=False)
    outlets["out-t2-pharma"] = dict(id="out-t2-pharma", name="Travel Health Hub intl", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="services", advertiser_id="adv-healthhub", dwell_focus=True)
    outlets["out-t2-simcards"] = dict(id="out-t2-simcards", name="SkyLink eSIM desk", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="services", advertiser_id="adv-skylink", dwell_focus=False)
    outlets["out-t2-lounge"] = dict(id="out-t2-lounge", name="Aurora Sky Lounge day passes", terminal="T2", zone_id="T2-8-gates", zone="T2 Concourse 8 gates", kind="services", advertiser_id="adv-auroralounge", dwell_focus=True)
    outlets["out-t2-chapel"] = dict(id="out-t2-chapel", name="Travel Health Hub pharmacy", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="services", advertiser_id="adv-healthhub", dwell_focus=False)
    outlets["out-t2-delights"] = dict(id="out-t2-delights", name="Sky Delights duty free", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="duty-free", advertiser_id="adv-meridian-retail", dwell_focus=False)
    outlets["out-t1-simcards"] = dict(id="out-t1-simcards", name="SkyLink eSIM desk T1", terminal="T1", zone_id=zid1, zone="T1 Retail corridor", kind="services", advertiser_id="adv-skylink", dwell_focus=False)
    outlets["out-t2-cellars-express"] = dict(id="out-t2-cellars-express", name="Harbour Cellars express", terminal="T2", zone_id=zid2, zone="T2 Retail corridor", kind="duty-free", advertiser_id="adv-cellars", dwell_focus=False)
    outlets["out-t2-sunwear-k"] = dict(id="out-t2-sunwear-k", name="Sunwear Co kiosk T2-5", terminal="T2", zone_id="T2-5-gates", zone="T2 Concourse 5 gates", kind="retail", advertiser_id="adv-sunwear", dwell_focus=False)
    # gate-adjacent F&B
    zgates1 = "T1-B-gates"
    zgates2 = "T2-1-gates"
    for i in range(5):
        outlets[f"out-gate-t1-k{i}"] = dict(id=f"out-gate-t1-k{i}", name=f"Harbour Roaster express T1-1{i}", terminal="T1", zone_id=zgates1, zone="T1 Concourse B gates", kind="coffee", advertiser_id="adv-harbour-roasters", dwell_focus=True)
        outlets[f"out-gate-t2-k{i}"] = dict(id=f"out-gate-t2-k{i}", name=f"Harbour Roaster express T2-2{i}", terminal="T2", zone_id=zgates2, zone="T2 Concourse 1 gates", kind="coffee", advertiser_id="adv-harbour-roasters", dwell_focus=True)
    return outlets


def build_advertisers() -> dict:
    return {
        "adv-aromatics": dict(id="adv-aromatics", name="Meridian Aromatics", category="beauty", colour="#e11d48"),
        "adv-harbour-roasters": dict(id="adv-harbour-roasters", name="Harbour Roasters Coffee", category="coffee", colour="#b45309"),
        "adv-sprockets": dict(id="adv-sprockets", name="Sprockets Toy Cellar", category="toys", colour="#7c3aed"),
        "adv-auroralounge": dict(id="adv-auroralounge", name="Aurora Sky Lounge", category="lounge", colour="#0e7490"),
        "adv-sugarbird": dict(id="adv-sugarbird", name="Sugarbird Sweets", category="confectionery", colour="#db2777"),
        "adv-skyline": dict(id="adv-skyline", name="Skyline Books", category="books", colour="#1d4ed8"),
        "adv-aerowear": dict(id="adv-aerowear", name="Aerowear Apparel", category="apparel", colour="#334155"),
        "adv-vista": dict(id="adv-vista", name="Vista Watch & Jewels", category="watches", colour="#8b5cf6"),
        "adv-sunwear": dict(id="adv-sunwear", name="Sunwear Co", category="beachwear", colour="#d97706"),
        "adv-cellars": dict(id="adv-cellars", name="Harbour Cellars", category="liquor", colour="#be123c"),
        "adv-skylink": dict(id="adv-skylink", name="SkyLink Telecom", category="telecom", colour="#0891b2"),
        "adv-healthhub": dict(id="adv-healthhub", name="Travel Health Hub", category="pharmacy", colour="#059669"),
        "adv-meridiandeli": dict(id="adv-meridiandeli", name="Meridian Deli Group", category="fnb", colour="#ca8a04"),
        "adv-sushibay": dict(id="adv-sushibay", name="Sushi Bay", category="fnb", colour="#0f766e"),
        "adv-meridian-retail": dict(id="adv-meridian-retail", name="Meridian Retail Group", category="fnb", colour="#475569"),
    }


def _creative(cid: str, campaign_id: str, headline_en: str, headline_alt: str, body_en: str, body_alt: str, bg: str, key: str, variant: str = "a", cta: str = "Scan to claim") -> dict:
    return dict(
        id=cid, campaign_id=campaign_id, variant=variant,
        headline_en=headline_en, headline_alt=headline_alt,
        body_en=body_en, body_alt=body_alt, cta=cta, bg=bg, fg="#ffffff", image=key, show_code=True,
    )


def build_campaigns() -> tuple[list[dict], dict[str, list[dict]]]:
    """25 campaigns: mix of APPROVED / PENDING / COMPLETE, all classification
    fields documented at docs/ARCHITECTURE. Gate-42 worked-example campaigns
    (wx-*) are defined separately in seed/worked_example.py."""
    zones = {
        "t2-1": "T2-1-gates", "t2-5": "T2-5-gates", "t2-6": "T2-6-gates", "t2-7": "T2-7-gates",
        "t2-8": "T2-8-gates", "t2-bus": "T2-BUS-gates",
        "t1-a": "T1-A-gates", "t1-b": "T1-B-gates", "t1-c": "T1-C-gates", "t1-bus": "T1-BUS-gates",
        "t1-retail": "T1-retail-main", "t2-retail": "T2-retail-main", "t1-sec": "T1-security",
        "t2-sec": "T2-security",
    }
    campaigns: list[dict] = []
    creatives: dict[str, list[dict]] = {}

    def add(
        cid: str, name: str, advertiser: str, outlet: str, status: str, *,
        domestic="any", min_intl=0.0, segments=None, dwell=0, crowd=0, zone_ids=(),
        terminal=None, hours=(5, 23), budget=1600.0, daily=420.0, freq=4, pacing=0.8,
        trigger="none", trigger_min=30, trigger_boost=1.0, festival=1.0, airline=None,
        airline_priority=False, cpm=1.4, dwell_floor=60.0, creatives_=None,
    ):
        campaigns.append(dict(
            id=cid, advertiser_id=advertiser, outlet_id=outlet, name=name, status=status,
            domestic=domestic, min_intl_share=min_intl, target_segments=segments or {},
            hard_dwell_min=dwell, min_crowd=crowd, zone_ids=list(zone_ids), terminal=terminal,
            hours_start=hours[0], hours_end=hours[1], budget_total=budget, daily_cap=daily,
            frequency_cap_per_screen_hour=freq, pacing_rate=pacing,
            trigger=trigger, trigger_delay_min=trigger_min, trigger_boost=trigger_boost,
            festival_day_boost=festival, airline_iata=airline, airline_priority=airline_priority,
            cpm=cpm, dwell_floor_min=dwell_floor,
        ))
        creatives[cid] = creatives_ or []

    # ---- approved retail campaigns ---------------------------------------
    add("cmp-df-perfume", "Aromatics — duty-free été 15% off", "adv-aromatics", "out-t2-df-perfume", "APPROVED",
        domestic="I", min_intl=0.40, segments={"international": 0.34, "holiday": 0.33, "adult25_54": 0.33},
        dwell_floor=53.0, zone_ids=[zones["t2-1"], zones["t2-5"], zones["t2-retail"]],
        creatives_=[
            _creative("cre-df-perfume-a", "cmp-df-perfume", "Signature perfume — 15% off duty free",
                      "Perfumería insignia — 15% dcto duty free",
                      "Ages 25–54, flying international: claim your sample set aroma chunk before boarding.",
                      "Vuelas internacional: reclama tu set de muestras antes del embarque.", "#9d174d", "motif-arc"),
        ])
    add("cmp-df-liquor", "Harbour Cellars — intl malt 20% off", "adv-cellars", "out-t2-df-liquor", "APPROVED",
        domestic="I", min_intl=0.5, segments={"adult25_54": 0.5, "premium": 0.5}, dwell_floor=45.0,
        zone_ids=[zones["t2-retail"], zones["t2-5"], zones["t2-6"]],
        creatives_=[_creative("cre-df-liquor", "cmp-df-liquor", "Single malt case — 20% off",
                              "Single malt — 20% dcto", "Exclusive aisle set at the Harbour Cellars counter.",
                              "Set exclusivo en Harbour Cellars.", "#7f1d1d", "motif-bottle")])
    add("cmp-toys", "Sprockets — buy 2 get 1 toy pack", "adv-sprockets", "out-t2-toys", "APPROVED",
        segments={"family": 0.34, "children": 0.33, "dwell": 0.33}, dwell_floor=54.0, crowd=40,
        zone_ids=[zones["t2-1"], zones["t2-5"], zones["t2-retail"]],
        creatives_=[_creative("cre-toys-a", "cmp-toys", "Kids flying? Buy 2 toys, get 1 free",
                              "¿Vuelan con niños? Llevas 2 juguetes y recoges 1 gratis",
                              "Keep the little ones busy until boarding. Claim at Sprockets.",
                              "Mantén a los niños distraídos hasta el embarque.", "#5b21b6", "motif-toys")])
    add("cmp-lounge", "Aurora Sky Lounge day pass", "adv-auroralounge", "out-t2-lounge", "APPROVED",
        domestic="I", min_intl=0.5, segments={"business": 0.5, "premium": 0.5}, zone_ids=[zones["t2-8"]],
        hours=(5, 22), creatives_=[_creative("cre-lounge", "cmp-lounge", "Aurora Sky Lounge day pass",
                                             "Pase diurno Aurora Sky Lounge", "Work, rest and showers before you board.",
                                             "Trabaja, descansa y ducha antes de embarcar.", "#155e75", "motif-lounge")])
    add("cmp-watches", "Vista Watches — limited drop", "adv-vista", "out-t2-watches", "APPROVED",
        segments={"premium": 0.6, "business": 0.4}, zone_ids=[zones["t2-retail"], zones["t2-6"]],
        creatives_=[_creative("cre-vista", "cmp-watches", "Vista limited edition at T2",
                              "Edición limitada Vista en T2", "Try the new Meridian dial today.",
                              "Prueba el nuevo dial Meridian hoy.", "#4c1d95", "motif-watch")])
    add("cmp-candy", "Sugarbird — sweets two for one", "adv-sugarbird", "out-t2-candy", "APPROVED",
        segments={"family": 0.34, "children": 0.33, "dwell": 0.33}, dwell_floor=52.0,
        zone_ids=[zones["t2-retail"], zones["t1-retail"], zones["t2-bus"], zones["t1-bus"]],
        creatives_=[_creative("cre-candy-a", "cmp-candy", "Two sweet packs, one price",
                              "Dos paquetes de dulces, un precio", "Family favourite — gift wrapping free.",
                              "Favorito familiar — empaque gratis.", "#9d174d", "motif-candy")])
    add("cmp-sunwear", "Sunwear beach kit", "adv-sunwear", "out-t2-sunwear", "APPROVED",
        domestic="I", segments={"holiday": 0.4, "family": 0.3, "children": 0.3},
        zone_ids=[zones["t2-5"], zones["t2-6"], zones["t2-retail"]],
        creatives_=[_creative("cre-sunwear", "cmp-sunwear", "Beach-ready before the bay",
                              "Listos para la playa", "Hats, sunscreen and beach mats in one bundle.",
                              "Sombreros, protector y esteras en un combo.", "#c2410c", "motif-sun")])
    add("cmp-books", "Skyline Books — holiday thriller", "adv-skyline", "out-t1-books", "APPROVED",
        segments={"business": 0.5, "adult25_54": 0.5}, zone_ids=[zones["t1-retail"], zones["t1-a"], zones["t1-c"]],
        creatives_=[_creative("cre-books", "cmp-books", "New in stores: Bayline thriller",
                              "Nuevo: thriller Bayline", "Long flight ahead? 10% off hardcovers.",
                              "¿Vuelo largo? 10% dcto en tapa dura.", "#0e7490", "motif-blob")])
    add("cmp-simcards", "SkyLink eSIM — land connected", "adv-skylink", "out-t2-simcards", "APPROVED",
        domestic="I", segments={"international": 0.4, "adult25_54": 0.3, "frequent": 0.3},
        zone_ids=[zones["t2-retail"], zones["t2-7"]],
        creatives_=[_creative("cre-skylink", "cmp-simcards", "Land connected — eSIM 10GB",
                              "Al aterrizar, conéctate — eSIM 10GB", "Scan to activate before your flight departs.",
                              "Escanea y activa antes de despegar.", "#0369a1", "motif-signal")])
    add("cmp-health", "Travel Health Hub — motion relief", "adv-healthhub", "out-t1-pharma", "APPROVED",
        segments={"family": 0.4, "adult25_54": 0.3, "dwell": 0.3}, dwell_floor=55.0,
        zone_ids=[zones["t1-retail"], zones["t2-retail"], zones["t1-b"]],
        creatives_=[_creative("cre-health", "cmp-health", "Motion comfort kit — 10% off",
                              "Kit de viaje — 10% dcto", "Cold spray, melatonin and wipes for family travellers.",
                              "Spray, melatonina y toallas para familia.", "#047857", "motif-cross")])
    add("cmp-sushi", "Sushi Bay express bento", "adv-sushibay", "out-t2-sushi", "APPROVED",
        segments={"business": 0.5, "adult25_54": 0.5}, zone_ids=[zones["t2-retail"], zones["t2-6"], zones["t2-7"]],
        creatives_=[_creative("cre-sushi", "cmp-sushi", "Express bento in 6 minutes",
                              "Bento expresso en 6 minutos", "Order ahead and skip the queue at Sushi Bay.",
                              "Pide antes y salta la fila.", "#134e4a", "motif-fish")])
    add("cmp-apparel", "Aerowear — cabin layer 25% off", "adv-aerowear", "out-t1-apparel", "APPROVED",
        segments={"business": 0.5, "adult25_54": 0.5}, zone_ids=[zones["t1-retail"], zones["t2-retail"], zones["t1-b"]],
        creatives_=[_creative("cre-apparel", "cmp-apparel", "Cabin layer — packable warmth",
                              "Capa de cabina — abrigo compacto", "25% off travel layers this week only.",
                              "25% dcto en capas de viaje esta semana.", "#0369a1", "motif-arc")])
    add("cmp-booksintl", "Skyline Books intl — travel guides", "adv-skyline", "out-t2-books", "APPROVED",
        domestic="I", segments={"international": 0.5, "adult25_54": 0.5},
        zone_ids=[zones["t2-retail"], zones["t2-7"], zones["t2-8"]],
        creatives_=[_creative("cre-booksintl", "cmp-booksintl", "Travel guides for the archipelago",
                              "Guías del archipiélago", "Field notes for Port Valen and Solmara.",
                              "Notas de Puerto Valen y Solmara.", "#0c4a6e", "motif-blob")])
    add("cmp-deliintl", "Meridian Deli intl — deli combo", "adv-meridiandeli", "out-t2-pizza", "APPROVED",
        segments={"adult25_54": 0.6, "dwell": 0.4}, dwell_floor=48.0,
        zone_ids=[zones["t2-retail"], zones["t2-6"], zones["t2-bus"]],
        hours=(6, 22),
        creatives_=[_creative("cre-deliintl", "cmp-deliintl", "Deli combo before you fly",
                              "Combo delicatessen antes de volar", "Half sandwich, soup and a drink.",
                              "Medio sándwich, sopa y una bebida.", "#854d0e", "motif-plate")])
    # ---- trigger / co-marketing ------------------------------------------
    add("cmp-delay-tonic", "Harbour Roasters — delayed-flight tonic", "adv-harbour-roasters", "out-t2-coffee", "APPROVED",
        segments={"business": 0.34, "adult25_54": 0.33, "dwell": 0.33}, dwell_floor=50.0,
        zone_ids=[zones["t2-5"], zones["t2-6"], zones["t1-b"], zones["t1-c"]],
        trigger="delay", trigger_min=25, trigger_boost=1.25,
        creatives_=[_creative("cre-tonic-a", "cmp-delay-tonic", "Delayed? First tonic on us",
                              "¿Vuelo demorado? Tónico de cortesía", "Show this screen at the counter for a free cold tonic.",
                              "Muestra esta pantalla en el mostrador.", "#431407", "motif-coffee")])
    add("cmp-boarding-coffee", "Harbour Roasters — boarding espresso", "adv-harbour-roasters", "out-gate-t1-k0", "APPROVED",
        terminal=None, zone_ids=[zones["t1-b"], zones["t1-c"]], trigger="boarding",
        trigger_boost=1.2, airline="YA", airline_priority=True,
        creatives_=[_creative("cre-boarding", "cmp-boarding-coffee", "Boarding YA? Espresso + cake",
                              "¿Embarcando YA? Espresso + pastel", "Aurora flyers claim at the bistro next to gate.",
                              "Pasajeros Aurora reclaman en el bistró.", "#78350f", "motif-coffee")])
    add("cmp-ya-goodwill", "Aurora — delay goodwill meal voucher", "adv-meridiandeli", "out-t1-deli", "APPROVED",
        terminal="T1", zone_ids=[zones["t1-a"], zones["t1-b"], zones["t1-c"], zones["t1-retail"]],
        trigger="delay", trigger_min=40, trigger_boost=1.6, airline="YA",
        creatives_=[_creative("cre-ya-meal", "cmp-ya-goodwill", "Delayed by Aurora? Meal on us",
                              "Demorado con Aurora? Comida de cortesía", "Show this at Meridian Deli: meal voucher for Aurora passengers.",
                              "Muéstralo en Meridian Deli.", "#065f46", "motif-plate")])
    add("cmp-arrival-sim", "SkyLink — arrivals data passes", "adv-skylink", "out-t2-simcards", "APPROVED",
        domestic="I", zone_ids=[zones["t2-retail"], zones["t2-8"], zones["t2-bus"]],
        creatives_=[_creative("cre-simcards2", "cmp-arrival-sim", "Just landed? Instant data",
                              "¿Acabas de aterrizar? Datos al instante", "Arrival eSIM desks open for the next hour.",
                              "Escritorios eSIM abiertos por una hora.", "#047857", "motif-signal")])
    # ---- pending (for media-manager approval surface) ---------------------
    add("cmp-pending-vista", "Vista — gift wrap campaign (pending)", "adv-vista", "out-t1-timew", "PENDING",
        zone_ids=[zones["t1-retail"], zones["t1-c"]],
        creatives_=[_creative("cre-vista2", "cmp-pending-vista", "Gift wrapping studio now open",
                              "Estudio de empaque abierto", "Bring your purchase for signature wrapping.",
                              "Trae tu compra y la empacamos.", "#6d28d9", "motif-gift")])
    add("cmp-pending-sushi", "Sushi Bay family menu (pending)", "adv-sushibay", "out-t2-sushi", "PENDING",
        segments={"family": 0.5, "children": 0.5}, zone_ids=[zones["t2-retail"], zones["t2-1"]],
        creatives_=[_creative("cre-sushi2", "cmp-pending-sushi", "Family bento box launch",
                              "Estreno: bento familiar", "Four-region set for family tables.",
                              "Cuatro regiones en un box.", "#115e59", "motif-fish")])
    add("cmp-pending-deli", "Meridian Deli late-night menu (pending)", "adv-meridiandeli", "out-t1-deli", "PENDING",
        hours=(19, 23), zone_ids=[zones["t1-retail"], zones["t1-bus"]],
        creatives_=[_creative("cre-deli", "cmp-pending-deli", "Late departures eat well",
                              "Salidas tardías comen bien", "Open until 23:00 at T1 Meridian Deli.",
                              "Abierto hasta las 23:00.", "#a16207", "motif-plate")])
    # ---- SCHEDULED/history (complete) ------------------------------------
    add("cmp-lob-liquor", "Harbour Cellars — completed autumn set", "adv-cellars", "out-t2-df-liquor", "COMPLETE", budget=2800.0, daily=800.0)
    add("cmp-hist-books", "Skyline Books — completed spring launch", "adv-skyline", "out-t2-books", "COMPLETE", budget=2200.0, daily=680.0)
    add("cmp-hist-gift", "Sprockets — completed holiday gifts", "adv-sprockets", "out-t1-toys", "COMPLETE", budget=1800.0, daily=520.0)
    # ---- airline boarding-window pause (airline-ads demo) -----------------
    add("cmp-lp-upgrade", "Lumen Pacific — upgrade lounge offer", "adv-auroralounge", "out-t2-lounge", "APPROVED",
        domestic="I", segments={"business": 0.5, "frequent": 0.5}, zone_ids=[zones["t2-8"], zones["t2-7"]],
        airline="YU", airline_priority=True, hours=(7, 22),
        creatives_=[_creative("cre-lp", "cmp-lp-upgrade", "Lumen Pacific — bid for an upgrade",
                              "Lumen Pacific — puja por upgrade", "Businesspod lounge access for top bidders.",
                              "Acceso lounge para mejores pujas.", "#0c4a6e", "motif-plane")])
    return campaigns, creatives


DEFAULT_CPM = 1.4
PROMO_VALUE: dict[str, float] = {
    "cmp-df-perfume": 15.0, "cmp-df-liquor": 22.0, "cmp-toys": 12.0, "cmp-lounge": 25.0,
    "cmp-candy": 6.0, "cmp-books": 8.0, "cmp-simcards": 10.0, "cmp-sushi": 9.0,
    "cmp-delay-tonic": 5.0, "cmp-ya-goodwill": 18.0, "cmp-health": 7.0, "cmp-apparel": 12.0,
    "cmp-sunwear": 9.0, "cmp-watches": 30.0, "cmp-arrival-sim": 10.0,
}


def build_promos(campaigns: list[dict], day: str, seed: int = 1013) -> list[dict]:
    rng = random.Random(seed + 77)
    rows: list[dict] = []
    base = datetime.fromisoformat(f"{day}T00:00:00+00:00")
    for c in campaigns:
        if c["status"] in ("PENDING", "COMPLETE"):
            continue
        value = PROMO_VALUE.get(c["id"], 0.0)
        n_windows = 6 if c["trigger"] != "none" else 4
        family = c["id"] in ("cmp-toys", "cmp-candy")
        for i in range(n_windows):
            hour = rng.choice([8, 9, 10, 12, 13, 14, 15, 16, 18, 19, 20, 21])
            start = base + timedelta(hours=hour, minutes=rng.choice([0, 15, 30]))
            end = start + timedelta(minutes=55)
            suffix = f"{rng.randrange(1000, 9999)}{rng.choice('ABCDEFGHJKLMNPQRSTUVWXYZ')}"
            rows.append(dict(
                id=f"pc:{c['id']}:{i}:std", run_id="", campaign_id=c["id"],
                code=f"{c['id'].split('-', 1)[1].upper()[:6]}{suffix}", kind="standard",
                window_start=start.isoformat(), window_end=end.isoformat(),
                flight_leg_id="", family_cap=2, value=value,
            ))
            if family and i % 2 == 0:
                rows.append(dict(
                    id=f"pc:{c['id']}:{i}:fam", run_id="", campaign_id=c["id"],
                    code=f"FAM{suffix}", kind="family",
                    window_start=start.isoformat(), window_end=end.isoformat(),
                    flight_leg_id="", family_cap=2, value=value,
                ))
    return rows


def build_history(campaigns: list[dict], day: str, seed: int = 1013) -> list[dict]:
    rng = random.Random(seed + 5)
    rows: list[dict] = []
    d0 = datetime.fromisoformat(f"{day}T00:00:00+00:00").date()
    for c in campaigns:
        if c["status"] == "PENDING":
            continue
        base_imp = rng.randrange(1800, 6800)
        conv = rng.uniform(0.02, 0.09)
        value = PROMO_VALUE.get(c["id"], 8.0)
        for dback in range(1, 31):
            d = d0 - timedelta(days=dback)
            wave = 1.0 + 0.4 * (d.weekday() >= 5) + 0.2 * math.sin(dback / 5)
            impressions = int(base_imp * wave * (0.8 + 0.4 * rng.random()))
            scans = int(impressions * conv * (0.8 + 0.4 * rng.random()))
            redemptions = int(scans * (0.45 + 0.2 * rng.random()))
            spend = round(impressions * c.get("cpm", DEFAULT_CPM) / 1000, 2)
            revenue = round(redemptions * value, 2)
            rows.append(dict(
                id=f"hist:{d.isoformat()}:{c['id']}", day=d.isoformat(), campaign_id=c["id"],
                impressions=impressions, scans=scans, redemptions=redemptions,
                spend=min(spend, c.get("budget_total", 900.0) / 30), revenue=revenue,
                is_history=True,
            ))
    return rows
