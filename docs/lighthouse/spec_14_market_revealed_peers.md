# Spec 14 — Market-Revealed Peers (who the MARKET thinks USIO's peers are)

**Status:** in progress. Lens (b) co-ownership building now; (a) co-movement and (c) coverage-overlap
sequenced behind it.
**Why:** the platform's peer analysis is built around peers WE and the company define — competitors, for
a valuation comp. But the *market* defines peers differently: by how securities actually co-move, by who
is co-held by the same managers, by supplier/customer links, and by shared sell-side coverage. The
market's peer can be a competitor, a supplier, a customer, or a market leader that drags the complex.
And the data says **USIO trades on its own**: its daily return correlates +0.23 with the small-cap index
but only ≤0.14 with any of its named payments peers; the peer basket explains ~3% of its variance
(Spec-13 factor loadings agreed — SMB 1.64, SEC −0.18). So our defined peers are a **fundamental** peer
set, not a **trading** peer set. This spec surfaces the market's revealed peer set and flags the
divergence — a genuinely useful, non-obvious IR message ("you trade on small-cap flow, not the sector").

Three revealed-peer lenses, each a different definition of "peer":

## (a) Co-movement — the statistical peer
Over a BROAD candidate universe (payments + fintech + card networks + merchant acquirers + the small-cap
complex, not just the 6 we picked), find the names USIO actually tracks via rank-correlation / a sparse
regression (elastic-net) that lets the DATA select the handful of names that explain USIO. Where the
revealed set diverges from our set, that's the finding; the winners can feed the attribution factor set
as a challenger.

## (b) Co-ownership — the capital-allocation peer — BUILT (lighthouse/coownership.py)

**First result (USIO, Q ending 31may2026) — triangulates the "trades on its own" finding:** of 25
holders fetched, **only 2 are focused/fundamental; 14 are quant/passive.** USIO is owned overwhelmingly
by flow vehicles. The 2 concentrated active managers (Perkins Capital, Investors Asset Mgmt of Georgia)
hold USIO alongside a *generalist* grab-bag — AMD, Eli Lilly, Natera, Butterfly Network, Axogen, Inuvo,
Equifax, QuickLogic, IDEXX, Backblaze — **not a payments cluster.** So the market's active capital does
NOT bucket USIO with its payments peers; it's a scattered small-cap held by generalist pickers + broad
flow. This agrees with the co-movement (+0.23 small-cap index vs ≤0.14 peers) and the factor loadings
(SMB 1.64, SEC −0.18): three independent lenses, one conclusion.


"Who owns USIO also owns ___." From 13F, aggregate USIO holders' OTHER holdings — the market's peer
grouping through who allocates capital, and the FLOW that actually moves a name trading on its own. We
already have the holder base and the 13F info-table plumbing (`core.sec_filings`).

**Methodology (the important part).** USIO's holders are mostly quant/passive/wealth vehicles whose books
hold *everything* (Whittier: 1,699 positions led by NVDA/AAPL/MSFT). Raw co-holding surfaces mega-caps,
not peers. So:
- restrict to **focused, fundamental** holders — non-mechanical (not the quant/index/MM stoplist) AND
  concentrated (≤ ~400 positions), the managers making a real small-cap *bet*;
- score each co-held name by the **sum of its portfolio weights across those focused holders** (a
  concentrated 40-name fund contributes far more per name than a 1,699-name book — this self-normalizes
  against index breadth and suppresses mega-caps), plus the focused-holder count;
- exclude USIO itself and broad ETFs.

**Deliverable:** `lighthouse/coownership.py` — cached batch (13F is quarterly, so refreshed on demand, not
daily), surfaced on the Lighthouse page. Output: the revealed peer list ("co-held by N of USIO's
concentrated active managers"), or the honest null result ("few concentrated active holders — owned via
broad/quant vehicles, consistent with trading on small-cap flow, not a fundamental peer complex").

## (c) Coverage overlap — the sell-side peer
Analysts covering USIO also cover ___ — the Street's revealed peer set, from the analyst rosters we
already track.

## Payoff
Surface the divergence: *"Your defined peers: […]. The market trades you with: the small-cap complex +
[co-held names]. Overlap: low."* Feeds both IR strategy (what actually moves the stock, who to target)
and the attribution engine (a data-revealed peer/factor challenger to the hand-picked basket).
