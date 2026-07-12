"""
data/seed/buyside_institutions.py — tracked buy-side institution roster for
the Investors > Buy-Side Intelligence tab.

This was an inline INSTITUTIONS list in the original single-file app.py
(hardcoded to USIO's actual tracked funds — Perkins, Vanguard, Rutabaga,
Ancora, Wasatch, BlackRock, Heartland, Dimensional). Moved here, keyed by
client_id, for the same multi-tenancy reason as data/seed/conferences.py:
client #2 will have a completely different set of tracked institutions,
not USIO's.

Each record is the RAW tracked data (holdings, call-listening behavior, IR
visit counts, turnover style, metro). The page computes Engagement_Score,
Score_Label, Score_Breakdown, and Digital_Intent_Score at render time
because those depend on which mode (pre/post-earnings) is active — they are
NOT stored here.

Coverage_Priority (1/2/3) is a manually-assigned IR coverage classification
— NOT the same thing as the live Engagement_Score-derived Tier 1/2/3 buckets
shown in the Investor Targeting Engagement Funnel (those recompute from real
signals every render; this is a static seed judgment call, same idea as
picking which accounts a sales rep owns). Renamed from the original demo's
plain "Tier" field after the two got confused with each other in the UI —
see investors_page.py's filter panel, labeled "Coverage priority" there.
"""

SEED_BUYSIDE_INSTITUTIONS = {
    "usio": [
        {
            "Fund": "Perkins Investment Management", "Type": "Small-Cap Value", "AUM": "$2.1B", "Coverage_Priority": 1,
            "USIO_Holder": True, "Shares": 485000, "QoQ_Change": 12000, "Call_Listener": True,
            "Listen_Duration": "Full replay (47 min)", "Peer_Holdings": ["GDOT", "PRTH"],
            "IR_Visits_30d": 4, "Last_Visit": "Jun 24, 2026", "Conviction": "High",
            "Call_Score": 40, "Peer_Score": 35, "Visit_Score": 25,
            "Turnover_Style": "Low (Long-Term Value)", "Metro": "Chicago / Midwest", "Ownership_Style": "Active",
            "Action": "Defend & expand — on the thesis, adding",
        },
        {
            "Fund": "Vanguard Group Inc", "Type": "Index / Passive", "AUM": "$8.2T", "Coverage_Priority": 2,
            "USIO_Holder": True, "Shares": 1450200, "QoQ_Change": 45000, "Call_Listener": False,
            "Listen_Duration": "—", "Peer_Holdings": ["GDOT", "EEFT", "PRTH"],
            "IR_Visits_30d": 1, "Last_Visit": "Jun 10, 2026", "Conviction": "Medium",
            "Call_Score": 0, "Peer_Score": 35, "Visit_Score": 10,
            "Turnover_Style": "Low (Long-Term Value)", "Metro": "New York Metro", "Ownership_Style": "Passive",
            "Action": "Passive — tracks index, maintain relationship",
        },
        {
            "Fund": "Rutabaga Capital Management", "Type": "Micro-Cap Specialist", "AUM": "$380M", "Coverage_Priority": 1,
            "USIO_Holder": False, "Shares": 0, "QoQ_Change": 0, "Call_Listener": True,
            "Listen_Duration": "38 min of 47 (81%)", "Peer_Holdings": ["PRTH", "EEFT"],
            "IR_Visits_30d": 6, "Last_Visit": "Jun 27, 2026", "Conviction": "High",
            "Call_Score": 38, "Peer_Score": 30, "Visit_Score": 25,
            "Turnover_Style": "Medium (Growth/GARP)", "Metro": "Boston / New England", "Ownership_Style": "Active",
            "Action": "🔥 HOT LEAD — not a holder, doing deep research",
        },
        {
            "Fund": "Ancora Advisors", "Type": "Small-Cap Value", "AUM": "$1.4B", "Coverage_Priority": 1,
            "USIO_Holder": False, "Shares": 0, "QoQ_Change": 0, "Call_Listener": True,
            "Listen_Duration": "Full replay (47 min)", "Peer_Holdings": ["GDOT", "PRTH"],
            "IR_Visits_30d": 3, "Last_Visit": "Jun 22, 2026", "Conviction": "High",
            "Call_Score": 40, "Peer_Score": 35, "Visit_Score": 20,
            "Turnover_Style": "Low (Long-Term Value)", "Metro": "New York Metro", "Ownership_Style": "Active",
            "Action": "🔥 HOT LEAD — owns peers, listened full call, 3 site visits",
        },
        {
            "Fund": "Wasatch Advisors", "Type": "Micro-Cap Growth", "AUM": "$17B", "Coverage_Priority": 2,
            "USIO_Holder": False, "Shares": 0, "QoQ_Change": 0, "Call_Listener": True,
            "Listen_Duration": "40 min of 47 (85%)", "Peer_Holdings": ["EEFT", "GDOT"],
            "IR_Visits_30d": 2, "Last_Visit": "Jun 15, 2026", "Conviction": "Medium",
            "Call_Score": 34, "Peer_Score": 35, "Visit_Score": 15,
            "Turnover_Style": "Medium (Growth/GARP)", "Metro": "West Coast (SF/LA)", "Ownership_Style": "Active",
            "Action": "Warm — owns peers, 2 site visits. Send deck.",
        },
        {
            "Fund": "BlackRock Small Cap Growth", "Type": "Momentum Growth", "AUM": "$9.8T", "Coverage_Priority": 2,
            "USIO_Holder": False, "Shares": 0, "QoQ_Change": 0, "Call_Listener": False,
            "Listen_Duration": "—", "Peer_Holdings": ["GDOT"],
            "IR_Visits_30d": 1, "Last_Visit": "May 30, 2026", "Conviction": "Low",
            "Call_Score": 0, "Peer_Score": 20, "Visit_Score": 10,
            "Turnover_Style": "High (Hedge/Trading)", "Metro": "New York Metro", "Ownership_Style": "Active",
            "Action": "Cold — GDOT holder only. Add to NDR list.",
        },
        {
            "Fund": "Heartland Advisors", "Type": "Small-Cap Value", "AUM": "$1.1B", "Coverage_Priority": 1,
            "USIO_Holder": False, "Shares": 0, "QoQ_Change": 0, "Call_Listener": True,
            "Listen_Duration": "22 min of 47 (47%)", "Peer_Holdings": ["PRTH"],
            "IR_Visits_30d": 2, "Last_Visit": "Jun 20, 2026", "Conviction": "Medium",
            "Call_Score": 25, "Peer_Score": 20, "Visit_Score": 15,
            "Turnover_Style": "Low (Long-Term Value)", "Metro": "Chicago / Midwest", "Ownership_Style": "Active",
            "Action": "Warm — partial listener. Follow up with Q2 preview.",
        },
        {
            "Fund": "Dimensional Fund Advisors", "Type": "Quant / Factor", "AUM": "$660B", "Coverage_Priority": 3,
            "USIO_Holder": True, "Shares": 220000, "QoQ_Change": -15000, "Call_Listener": False,
            "Listen_Duration": "—", "Peer_Holdings": ["GDOT", "EEFT", "PRTH"],
            "IR_Visits_30d": 0, "Last_Visit": "Apr 12, 2026", "Conviction": "Low",
            "Call_Score": 0, "Peer_Score": 35, "Visit_Score": 0,
            "Turnover_Style": "High (Hedge/Trading)", "Metro": "New York Metro", "Ownership_Style": "Active",
            "Action": "⚠️ Reducing — quant trim. Monitor position.",
        },
    ],
}


def get_seed_buyside_institutions(client_id):
    return [dict(i) for i in SEED_BUYSIDE_INSTITUTIONS.get(client_id, [])]
