You write a short, first-person message to a hiring team.

Job: {job_title} at {company}
Location: {location}
Job description:
{job_description}

Candidate profile (JSON):
{profile}

Long-term themes / memory pack:
{memory}

Questions to answer (JSON keys are question ids):
{questions}

Rules:
- Write in {language}.
- 150-300 Chinese characters (or 80-200 English words).
- Do not list CV projects; the CV already has them.
- Use concrete, high-level thinking; no slogans, no parallelism, no "赋能/闭环/生态".
- Avoid "正是我想体验的", "让数据说话", "如果有机会".
- Every factual claim must be supported by the profile or memory pack.
- Return JSON only: {{"message": "...", "answers": {{"question_id": "..."}}}}.
