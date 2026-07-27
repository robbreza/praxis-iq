# Focused Target List reconciliation (Jul 2026)

Reconciliation of a user-supplied regional "Focused Target List of Investors" (~505 accounts,
names only, by region: NY / Mid West / West Coast / Boston / Mid-Atlantic-South / Canada) against
the house CRM, followed by a verify-and-roster build-out of the keepers.

## Method
1. `compare_targetlist.py` — normalized fuzzy diff of the 505 accounts vs distinct CRM firms.
   Result: **266 already in the CRM (53%), 239 not matched.**
2. Six region verify+roster agents (CFA-rigor, no fabrication) assessed the 239 gaps. Rule:
   INCLUDE if still operating AND would host/attend a management meeting — **including hedge funds,
   long-only managers, and family offices that still invest in public equities and take meetings**
   (per the user, several closed-to-outside-money shops still take meetings). REJECT only if truly
   defunct/wound-down, fully merged (successor named), or a pure bank / broker-dealer / PE buyout /
   HFT / public pension.
3. `ingest_{nya,nyb,midwest,westcoast,boston,midatl_ca}.py` — rostered the verified firms
   (deduped against existing CRM firms). ~269 new contacts across ~90 firms.

## Disposition highlights
The list read as **dated (~2014–16, RBC-era)** — a large share of the missing NY/Boston hedge
funds had wound down or become family offices. Representative REJECTS with reasons:

- **Defunct / wound-down (EDGAR last-13F in parens):** George Weiss (Ch.11, 2024), Principled (2007),
  Ridgecrest (2013), Searock (2008), Sursum (2011), Thrax (2017), TriOaks (2014), Espalier (2016),
  Bascom Hill (2012), Ivory (2018), Oliver Press (2009), Owenoke (2010), Pacific Grove (2019),
  Vinik (no outside-capital vehicle), Stark, Independence, John McStay.
- **Merged / rebranded (successor):** Teton Advisors→Gabelli · QS Investors→Franklin Templeton ·
  U.S. Trust→BofA Private Bank · Babson→Barings · Mellon Growth→BNY/Mellon Investments ·
  WPG Partners→Robeco USA · Pioneer/Amundi US→Victory Capital · Rainier→Manning & Napier ·
  Analytic→Allspring · Denver Investments→Segall Bryant · Woodway→Westwood · Ridgeworth/Trusco→Virtus ·
  Gluskin Sheff→RBC/Onex · Goodman→Next Edge · GWL→Mackenzie/Canada Life · Invesco Trimark→Invesco/CI ·
  Sentry→CI · Natcan→NBI · Pyramis→FIAM/Fidelity · Northern Rivers→Aston Hill(defunct) · MFC Global→Manulife.
- **Wrong entity type:** Aptigon/Catapult/Pioneer Path (Citadel/Millennium pods, absorbed) ·
  DB Alternative Trading (ATS) · Peak6 (options MM) · Big Basin/Harpoon (VC) · Platte River/Gyrus
  (PE) · Constitution (PE/credit) · Fosun (conglomerate) · Jafra (cosmetics) · Ozumo (restaurant).

## Open items (NOT yet resolved — for a follow-up pass)
- **Whalerock (Boston)** — user knows it personally (ex-MFS/Fidelity boutique) but no such Boston
  firm could be verified (only "Whalerock Point Partners", a West Palm Beach FL wealth RIA). Needs
  the correct firm name from the user.
- **Verified but no roster** (firm confirmed operating, people not sourced before search budget ran
  out): Madera, Anchor Bolt, Carnegie, Copia, Heitman, Nationwide, Parkwest, Sheffield, Shine,
  Brookside/Bain Public Equity, John Hancock, LMCG, Pangaea, Putnam, AGF, Barometer, IGM, Polar,
  1838, Afton, abrdn(dup), CI Global(dup), 1832(dup), TD(dup). Re-run for rosters.
- **Unconfirmed (search budget exhausted, not confirmed dead):** Acrospire, Blue Rock, Brazos,
  Cloverdale, Continental, IronBridge. Re-verify before writing off.

## Coverage note
`compare_targetlist.py` matching is fuzzy/normalized — a few big names may be present under a
variant or missed; spot-check before treating a single "not in DB" flag as authoritative.
