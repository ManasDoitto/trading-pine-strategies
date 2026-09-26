# Results: SILVERM short-only option-buying variant (run 2026-09-26)

Pre-registration: `pre_registration_silverm_shortonly_2026_09_26.md`. Gross points, 30 months, six calendar windows,
measured skew CE 31.4% / PE 21.5%, v4.0 wide-ATR + 350 signal unchanged.

## Verdict: FAILS criterion A. The short-only variant is NOT supported, despite a better headline number.

| | PE beat CE in | needed |
|---|---|---|
| **Criterion A** | **3 of 6 windows** | >= 4 |
| **Criterion B** (futures must not be short-biased) | futures SHORT beat LONG in 2 of 6 - **PASSES** | |
| **Criterion C** (V2 beats V1 at 1%) | +44,832 vs +52,051 net; PF 1.388 vs 1.200 - **mixed** | |

Criterion A fails, so by the pre-registered rule the variant is reported as unsupported. It would have been easy to
report "short-only lifts PF from 1.200 to 1.388 and survives a 2% spread where both-sides does not" and stop there.

## The control that matters: this is the skew, but it is not consistent
**Criterion B passes cleanly, and that part is a real finding.** The underlying futures strategy is LONG-biased, not
short-biased: futures longs earned **+80,456** on 401 trades (+200.6 avg) against shorts' **+46,119** on 331 (+139.3 avg),
and shorts beat longs in only 2 of 6 windows. Yet the option book inverts completely - CE +7,219 vs PE +44,832.
A strategy whose futures profit is 64% long turns into an option book whose profit is 86% short. That inversion can
only come from pricing: 4,517 pts of premium for a call against 2,949 for a put at the same ATM distance.
**So the skew is genuinely eating the long side.** That much is established and is the useful takeaway.

## But the PE advantage is concentrated, not persistent
| window | fut LONG | fut SHORT | opt CE | opt PE | PE > CE? |
|---|---|---|---|---|---|
| W1 | +7,703 | +4,282 | -223 | -258 | no |
| W2 | +12,261 | +4,009 | +1,576 | -326 | no |
| W3 | +4,017 | +4,660 | -4,023 | +595 | YES |
| W4 | +21,695 | +6,899 | +4,382 | +2,650 | no |
| W5 | +26,951 | -8,557 | +11,768 | +26,160 | YES |
| W6 | +7,829 | +34,827 | -6,262 | +16,012 | YES |

PE wins only half the windows, and **+42,172 of the PE side's +44,832 comes from W5 and W6 alone** (94%). W5 is the
same Nov 2025-Apr 2026 window that carries 61% of the silver futures strategy's entire profit, and in W5 the futures
short book actually **lost** -8,557 while the option put book made +26,160 - the skew paying out, but in one window.
This is the third time in this session that a strong number resolved to one stretch of silver.

## The variant's numbers, for the record (not a recommendation)
| spread/side | V1 both sides | **V2 short-only** | V3 long-only |
|---|---|---|---|
| 0% | PF 1.486, +108,890 | PF 1.631, +65,007 | PF 1.363, +43,884 |
| 0.5% | PF 1.332, +80,471 | PF 1.502, +54,920 | PF 1.193, +25,551 |
| **1%** | PF 1.200, **+52,051** | PF 1.388, **+44,832** | PF 1.050, +7,219 |
| 2% | PF 0.984, **-4,789** | PF 1.192, **+24,658** | PF 0.825, -29,447 |

V2 does have the better risk profile - higher PF at every spread, drawdown 22,304 vs 32,797 at 1%, and it is the only
variant still positive at a 2% spread. But it earns **fewer net points** than V1 at the spread levels that matter
(+44,832 vs +52,051 at 1%), on half the trades, and it fails the persistence test. By the user's own net-points
standard it is a smaller strategy, not a better one.

## What is actually supported
1. **The CE/PE skew is real, measured, and materially damages the long side of any option-buying version of this
   strategy.** A futures book that is 64% long becomes an option book that is 86% short purely through pricing.
2. **Short-only is not the right response**, because the put advantage does not hold up window by window - it is two
   windows out of six, one of which is the same outlier window that dominates everything else in this silver family.
3. A better-motivated response, untested: **require a larger expected move before paying for a call** (raise the
   target or tighten entry quality on longs only), rather than discarding the long side that earns +80,456 in futures.

## Bottom line
Reported as unsupported per criterion A. The skew finding stands; the short-only variant does not.
