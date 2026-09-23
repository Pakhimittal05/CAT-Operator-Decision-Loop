# Six Product Concepts

Each concept is one coherent system, not a feature list. All five required areas are addressed inside a single closed-loop architecture, built around a different unifying idea per concept.

---

## 1. PRODUCT NAME
**Ready** — the Operator Readiness Copilot

## 2. ONE-SENTENCE CONCEPT
A system that maintains a continuously updated "readiness state" per operator (fatigue, alert-response quality, recent anomalies) and uses that single state to drive task sequencing, alert behavior, and time estimates.

## 3. CORE PROBLEM
Today's dashboard, safety alerts, and time estimates all ignore the operator's *current* condition — they treat every hour of a shift as identical.

## 4. USER JOURNEY
Operator clocks in; sees today's tasks reordered by readiness (easy task first if readiness is low). Mid-shift, a proximity alert fires — the system checks recent alert-response history and escalates tone/channel only if compliance is decaying. End of shift, operator sees why tasks were sequenced that way and can override with a reason (feedback loop).

## 5. HOW IT HANDLES THE FIVE AREAS
- **Daily tasks:** dynamically re-ranked by readiness score, not static list.
- **Safety:** seatbelt/proximity alerts modulate escalation based on the readiness-weighted compliance model.
- **Training:** low-readiness patterns for specific task types trigger targeted refresher suggestions.
- **Unusual behavior:** idling/pattern anomalies interpreted relative to the operator's own readiness baseline, not a global threshold.
- **Time estimation:** predicted duration includes a readiness-adjusted interval, with explanation.

## 6. CORE INNOVATION
A single latent "readiness" variable feeds all four other modules, instead of four independent scripts.

## 7. AI/ML COMPONENTS
Lightweight state-space/Bayesian model updating readiness from shift length, alert history, anomaly rate; gradient-boosted regressor with prediction intervals for time estimation.

## 8. DATA REQUIRED
Shift timestamps, alert logs with response times, telemetry per task, weather, skill label.

## 9. SYNTHETIC DATA STRATEGY
Generate multi-day shifts per synthetic operator with an injected readiness-decay curve (fatigue increasing, compliance dropping); validate that the model recovers the injected curve.

## 10. CLOSED-LOOP BEHAVIOR
Observe telemetry/alerts → infer readiness → recommend task order/alert tone → operator accepts or overrides → outcome (compliance, time, incident) logged → readiness model recalibrated nightly.

## 11. 5-MINUTE DEMO
Show two synthetic operators, same tasks, different readiness trajectories → different task order, different alert escalation, different time-estimate confidence bands, then show a slow-decay operator triggering a supervisor notification.

## 12. BIGGEST TECHNICAL RISK
Readiness is unobservable; the proxy signals (idle time, response latency) are noisy, so the model may overfit synthetic patterns that don't generalize.

## 13. BIGGEST JUDGE QUESTION
"How do you know 'readiness' isn't just idling time relabeled?"

## 14. HOW ANOTHER TEAM COULD COPY IT
Any team could bolt a rolling-average "fatigue score" onto a dashboard in a day.

## 15. HOW TO MAKE IT HARDER TO COPY
(a) Make readiness a *learned latent variable* from multiple signals via a proper state-space model with uncertainty, not a hand-tuned formula; (b) require the readiness model to justify itself with feature attribution shown to the operator, forcing real interpretability work.

---

## 1. PRODUCT NAME
**Why, Not Just What** — Causal Safety & Coaching Loop

## 2. ONE-SENTENCE CONCEPT
Every anomaly the system flags comes with a probable cause, and causes that trace back to skill gaps automatically become personalized coaching content.

## 3. CORE PROBLEM
Anomaly flags without explanation breed operator distrust; training content without behavioral grounding doesn't fix the actual gap.

## 4. USER JOURNEY
Operator gets flagged for high idling; instead of a warning, sees "likely cause: queue wait (87% confidence)" — no blame. A different flag on load-cycle timing shows "likely cause: technique gap vs. expert baseline" and links directly to a 90-second coaching clip built from the expert/beginner telemetry comparison for that exact task type.

## 5. HOW IT HANDLES THE FIVE AREAS
- **Daily tasks:** unaffected structurally, but annotated with "coaching due" markers.
- **Safety:** incident logging captures the causal tag, not just the raw event.
- **Training:** auto-generated micro-coaching from expert-vs-operator telemetry diffs, replacing generic e-learning.
- **Unusual behavior:** classified into cause buckets (mechanical, environmental, technique, disengagement) instead of one flag type.
- **Time estimation:** cause labels become features/explanations in the estimate.

## 6. CORE INNOVATION
The anomaly detector and the training hub share one causal model — training content is *generated from* attributed anomalies, not authored separately.

## 7. AI/ML COMPONENTS
Multi-class cause classifier (rule-assisted + ML) using cross-machine/weather/task context; nearest-neighbor comparison against expert telemetry signatures for coaching content generation.

## 8. DATA REQUIRED
Multi-machine telemetry, task schedules, weather logs, skill labels, per-task expert/beginner signatures.

## 9. SYNTHETIC DATA STRATEGY
Construct identical idle-time signatures with different generating causes (queue wait vs. fault vs. disengagement) so the classifier's job is demonstrably non-trivial; construct expert vs. beginner signature pairs per task type.

## 10. CLOSED-LOOP BEHAVIOR
Observe anomaly → classify cause → if technique-related, recommend coaching clip → operator completes/skips → next session's telemetry compared to baseline → coaching engine updates whether the gap closed.

## 11. 5-MINUTE DEMO
Trigger three anomalies with identical raw signature but different injected causes; show correct cause classification each time, then show one auto-generating a coaching card with a specific numeric technique gap.

## 12. BIGGEST TECHNICAL RISK
Cause attribution from a handful of correlated signals is inherently weak; confident wrong causes could be worse than no explanation.

## 13. BIGGEST JUDGE QUESTION
"What stops this from confidently mis-attributing blame anyway?"

## 14. HOW ANOTHER TEAM COULD COPY IT
A simple decision tree with "if idling AND no other machines idle THEN disengagement" looks similar on the surface.

## 15. HOW TO MAKE IT HARDER TO COPY
(a) Output calibrated probabilities across causes (not single label) and only auto-generate coaching above a confidence threshold, with the model showing its reasoning; (b) close the loop by measuring whether coaching actually shrank the technique gap in subsequent sessions, and feed that back into cause-classifier confidence.

---

## 1. PRODUCT NAME
**Horizon** — Leading-Indicator Site Risk Engine

## 2. ONE-SENTENCE CONCEPT
A system that treats safety as a sequence-prediction problem across the whole site, warning operators and managers before a threshold-triggering incident, not after.

## 3. CORE PROBLEM
Standard safety systems only react once a threshold is crossed; the real risk builds up beforehand and often involves more than one machine.

## 4. USER JOURNEY
Operator's dashboard shows a rising site-risk indicator as two machines' paths begin converging, well before any proximity threshold fires. Manager sees the same signal site-wide and can reroute a machine. If ignored, the system escalates. At day's end, a report shows which early warnings preceded real incidents vs. false alarms.

## 5. HOW IT HANDLES THE FIVE AREAS
- **Daily tasks:** task ordering incorporates predicted site-risk windows.
- **Safety:** proximity/seatbelt alerts are pre-empted by sequence-based early warnings; incident logging includes the precursor sequence, not just the event.
- **Training:** operators whose sessions repeatedly show late-stage precursor patterns get flagged for targeted coaching.
- **Unusual behavior:** idling/pattern anomalies are inputs to the precursor sequence model, not standalone flags.
- **Time estimation:** high-risk windows widen the time-estimate uncertainty band.

## 6. CORE INNOVATION
Modeling incidents as the *tail end of a sequence* across multiple machines, rather than independent, single-machine threshold events.

## 7. AI/ML COMPONENTS
Sequence model (HMM or small RNN/transformer) trained on time-ordered multi-machine telemetry to detect ramping precursor patterns; simple spatial convergence estimator from position/heading.

## 8. DATA REQUIRED
Time-ordered, multi-machine telemetry with position/heading, timestamped alerts/incidents.

## 9. SYNTHETIC DATA STRATEGY
Simulate two-machine trajectories on a shared grid, injecting a known precursor ramp (rising idle + erratic load cycles + closing distance) before a labeled "incident," and show the model firing a warning before the threshold event.

## 10. CLOSED-LOOP BEHAVIOR
Observe sequence → estimate risk trajectory → recommend reroute/slowdown → operator/manager acts or ignores → log actual outcome → retrain risk thresholds on which warnings preceded real incidents vs. resolved themselves.

## 11. 5-MINUTE DEMO
Animate two synthetic machines converging on a shared grid; show the risk score climbing and a warning firing well before the proximity alert would have; show a false-positive case where risk fell back down, illustrating calibration.

## 12. BIGGEST TECHNICAL RISK
Sequence models need substantial time-series data to avoid overfitting a single injected pattern; multi-machine spatial data may not be realistically simulable without real GPS traces.

## 13. BIGGEST JUDGE QUESTION
"Isn't this just a proximity alert with extra steps?"

## 14. HOW ANOTHER TEAM COULD COPY IT
A distance-threshold-with-a-buffer-zone approach looks similar without the sequence modeling.

## 15. HOW TO MAKE IT HARDER TO COPY
(a) Require the model to predict *how many seconds until* convergence, not just a binary flag — this needs real trajectory forecasting, not a static buffer; (b) build the outcome-feedback loop that reclassifies past warnings as true/false positives and recalibrates thresholds, which most teams skip entirely.

---

## 1. PRODUCT NAME
**Ledger** — Living Skill & Trust Profile

## 2. ONE-SENTENCE CONCEPT
Replaces the static "Expert/Intermediate/Beginner" label with a continuously updated, task-specific skill score that drives training, task assignment, and time estimation together.

## 3. CORE PROBLEM
A frozen skill label silently caps the accuracy of every downstream feature and gives operators no way to demonstrate genuine improvement or flag decay.

## 4. USER JOURNEY
Operator sees a per-task-type skill score (not a badge) that moved up this week after several efficient sessions. A task requiring a skill they haven't used in months shows a decay warning and a suggested refresher before assignment. Time estimates for their tasks now use their live score rather than a stale label.

## 5. HOW IT HANDLES THE FIVE AREAS
- **Daily tasks:** assignment weighted by current per-task skill score and decay risk.
- **Safety:** low current-skill + high-risk task combination triggers stricter alert sensitivity for that operator.
- **Training:** refreshers are targeted at specific decayed skills, not generic modules; instructor booking suggested only when decay is severe.
- **Unusual behavior:** deviations are compared against the operator's *own current* skill trajectory, catching decay before it becomes a safety event.
- **Time estimation:** skill score is a live feature with explicit contribution shown.

## 6. CORE INNOVATION
Skill becomes a state variable with memory and decay, not a static field — every other module reads from it.

## 7. AI/ML COMPONENTS
Time-decayed performance scoring (e.g., exponentially weighted moving statistics per task type) with confidence intervals; feature-attribution regressor for time estimation.

## 8. DATA REQUIRED
Longitudinal per-operator, per-task-type performance history across weeks/months.

## 9. SYNTHETIC DATA STRATEGY
Simulate an operator improving, then having a multi-week gap, then decaying, then recovering after a refresher; show the live score tracking this while a frozen label would stay wrong throughout.

## 10. CLOSED-LOOP BEHAVIOR
Observe session performance → update skill score → recommend refresher/task fit → operator takes or skips refresher → next session's performance measured → score and decay-rate model recalibrated.

## 11. 5-MINUTE DEMO
Show the score chart for one synthetic operator across a simulated year with a gap and recovery, next to the static label that never changes; show a task-assignment screen refusing to assign a high-risk task without a refresher.

## 12. BIGGEST TECHNICAL RISK
Decay rates are essentially invented without real longitudinal operator data — the parameters are guesses, and the demo has to be honest about that.

## 13. BIGGEST JUDGE QUESTION
"How is this different from a moving average with a friendlier UI?"

## 14. HOW ANOTHER TEAM COULD COPY IT
A rolling average of recent performance metrics could superficially replicate this in an afternoon.

## 15. HOW TO MAKE IT HARDER To COPY
(a) Model decay explicitly as a function of *time since last practice per task-type*, not just recency-weighted averaging — this requires survival/decay modeling, not a moving average; (b) make the score portable and exportable as a structured credential artifact, forcing a real data schema and versioning story most teams won't bother building.

---

## 1. PRODUCT NAME
**Ground Truth** — Sensor-Trust Assistant

## 2. ONE-SENTENCE CONCEPT
Every downstream feature (safety, anomaly detection, time estimation) consumes a confidence-weighted, self-checked version of the telemetry instead of raw sensor values.

## 3. CORE PROBLEM
All four other required features silently assume telemetry is correct; a single bad sensor reading can produce confidently wrong safety and behavior conclusions.

## 4. USER JOURNEY
Operator's dashboard shows tasks and alerts as usual, but a small indicator flags when a reading (e.g., fuel-use rate) is inconsistent with related signals (engine hours, load cycles). Manager sees a site-wide "data health" view. When a sensor is flagged unreliable, the anomaly detector and time estimator visibly widen their uncertainty rather than pretending precision.

## 5. HOW IT HANDLES THE FIVE AREAS
- **Daily tasks:** dashboard shows task confidence downgraded when a machine's sensors are flagged.
- **Safety:** alerts suppress false triggers caused by known-bad sensor readings, and never suppress silently — they say why.
- **Training:** none directly, but operators are trained on interpreting confidence indicators (still satisfies training hub requirement via a dedicated module).
- **Unusual behavior:** implausible-reading detection is itself a class of "unusual" pattern, feeding the anomaly module rather than being separate from it.
- **Time estimation:** prediction intervals widen automatically when input data quality is low.

## 6. CORE INNOVATION
Data-quality checking as a first-class module that every other feature must consult, rather than an afterthought.

## 7. AI/ML COMPONENTS
Cross-field consistency model (e.g., regression residuals between fuel-use rate, load cycles, engine-hour delta) to score plausibility; propagation of that confidence score into downstream model uncertainty.

## 8. DATA REQUIRED
Same telemetry fields already provided — no new data sources needed.

## 9. SYNTHETIC DATA STRATEGY
Inject a controlled set of corrupted/implausible rows (physically inconsistent fuel/engine-hour combinations) into an otherwise clean synthetic stream, and show detection precision/recall on the injected set.

## 10. CLOSED-LOOP BEHAVIOR
Observe raw telemetry → score consistency → flag/downweight suspect readings → downstream modules adjust confidence → operator/manager reviews flagged sensor → resolution logged → consistency thresholds recalibrated from confirmed true/false flags.

## 11. 5-MINUTE DEMO
Stream synthetic telemetry with a few injected corrupted rows live; show the consistency score dropping exactly on those rows and the downstream time-estimate uncertainty band visibly widening at the same moment.

## 12. BIGGEST TECHNICAL RISK
Distinguishing "real anomalous machine behavior" from "sensor fault" is genuinely hard and the two are easy to confuse in synthetic data.

## 13. BIGGEST JUDGE QUESTION
"Isn't this just outlier detection on individual columns?"

## 14. HOW ANOTHER TEAM COULD COPY IT
Z-score outlier flags on each column independently would look similar at a glance.

## 15. HOW TO MAKE IT HARDER TO COPY
(a) Require cross-*field* physical-consistency checks (residuals between related signals) rather than single-column outlier detection, which needs a small learned relationship model, not a threshold; (b) show the confidence score actually changing the numeric output of the time-estimator and anomaly detector live, proving it's wired through the pipeline rather than a decorative badge.

---

## 1. PRODUCT NAME
**Rehearsal** — What-If Scheduling Cockpit

## 2. ONE-SENTENCE CONCEPT
Lets a site manager simulate reassigning operators, tasks, or machines and see predicted risk, time, and skill-fit changes before committing, then tracks whether reality matched the simulation.

## 3. CORE PROBLEM
Task/operator assignment is currently a one-shot administrative decision with no way to compare alternatives or learn whether past decisions were good ones.

## 4. USER JOURNEY
Manager opens tomorrow's plan; drags a task from one operator to another and instantly sees updated time estimate (with uncertainty), skill-fit score, and predicted risk level for that swap. Commits the plan. Next day, actual outcomes are compared against the simulated prediction, and the discrepancy is shown back to the manager.

## 5. HOW IT HANDLES THE FIVE AREAS
- **Daily tasks:** the dashboard *is* the simulation surface — every reassignment is a what-if run before commitment.
- **Safety:** simulated assignments show predicted risk given operator readiness/skill/history, not just after the fact.
- **Training:** simulation surfaces "this operator would benefit from a refresher before this reassignment" recommendations.
- **Unusual behavior:** past anomaly patterns for an operator-task-machine combination are folded into the simulated risk score.
- **Time estimation:** the core output of every simulated scenario, shown with confidence intervals per scenario.

## 6. CORE INNOVATION
Turns the dashboard from a passive record into a decision-rehearsal tool with a real prediction-vs-outcome feedback loop.

## 7. AI/ML COMPONENTS
The same time-estimation and risk models as other concepts, but exposed as a queryable "simulate(operator, task, machine, conditions)" function; a lightweight tracker comparing predicted vs. actual outcomes over time.

## 8. DATA REQUIRED
Historical task/operator/machine outcomes, skill labels, weather, alert/incident history.

## 9. SYNTHETIC DATA STRategy
Generate a synthetic historical log, train the estimator/risk model on it, then run manager "what-if" swaps and show internally consistent predictions changing sensibly across scenarios (e.g., swapping in a beginner raises both time and risk).

## 10. CLOSED-LOOP BEHAVIOR
Observe historical outcomes → build predictive models → manager simulates scenarios → commits one → real (synthetic) outcome recorded → predicted-vs-actual gap computed → models recalibrated, and the gap itself is shown to build manager trust or distrust appropriately.

## 11. 5-MINUTE DEMO
Live drag-and-drop reassignment of a task between two synthetic operators, showing time/risk/skill-fit numbers update instantly for each candidate; then show a "yesterday's simulated plan vs. actual outcome" comparison screen.

## 12. BIGGEST TECHNICAL RISK
Interactive what-if requires the underlying models to be fast and stable across many hypothetical inputs, not just accurate on one historical test set — brittle models will produce nonsensical scenario comparisons.

## 13. BIGGEST JUDGE QUESTION
"Are the underlying predictions actually good, or is this just a nice UI over noise?"

## 14. HOW ANOTHER TEAM COULD COPY IT
A form that recalculates a single regression output when you change a dropdown looks superficially similar.

## 15. HOW TO MAKE IT HARDER TO COPY
(a) Require every simulated scenario to also report *uncertainty*, and make scenarios with less historical support show visibly wider bands — this needs real interval estimation, not a point-prediction refresh; (b) build the actual predicted-vs-outcome tracking loop and show it changing model behavior over multiple simulated "days," which is a genuine pipeline, not a static form.