# MealMatch User Study: Ethics and Data-Management Plan

> **Working checklist, not legal advice.** Confirm the final process with the
> module supervisor, [LOCAL COLLEGE] ethics contact and Goldsmiths departmental
> ethics contact before recruiting anyone.

## 1. Approval and applicable standards

Because the project involves living human participants and data derived from
their interaction, obtain ethics approval before recruitment or pilot data
collection. Goldsmiths states that student-led undergraduate research approval
is managed by the relevant academic department. As the study will be conducted
in Singapore through an overseas-college programme, ask for written
confirmation of:

1. which Goldsmiths or programme ethics form and committee apply;
2. whether [LOCAL COLLEGE] requires a separate or joint approval;
3. which institution is the data controller and which is a processor;
4. the approved storage platform and retention/deletion date;
5. the current mandatory Goldsmiths participant privacy notice; and
6. whether any identifiable data may be accessed from or transferred to the UK.

The practical protocol should meet both the approved Goldsmiths/UK requirements
and Singapore's PDPA requirements. Singapore's PDPA requires notification of
purpose, appropriate consent where relied upon, reasonable security, retention
limits and controls on overseas transfers. UK GDPR and the Data Protection Act
2018 may also apply where Goldsmiths determines the purpose and means of
processing or receives personal data. Do not decide the controller or legal
basis yourself; record the institutions' determination in the ethics
application and participant notice.

## 2. Low-risk study design

- Recruit adults aged 18 or over only.
- Use standardised researcher-provided photographs, receipts, pantry contents,
  recipes and fictional dietary/allergy scenarios.
- Do not collect actual medical conditions, allergies, religion or ethnicity.
- Do not photograph participants or their homes.
- Do not make screen, video or persistent voice recordings.
- Explain that microphone audio is processed transiently by the local backend
  and deleted immediately after transcription.
- Instruct participants not to enter names, contact details or confidential
  information into the prototype.
- Do not ask participants to cook, eat food or follow safety-critical advice.
- Allow questions to be skipped and sessions to stop without consequence.

## 3. Data inventory

| Data | Purpose | Identifiability | Retention |
|---|---|---|---|
| Signed consent form | Evidence of informed consent | Directly identifiable | Separate encrypted folder until [DATE] |
| Contact details, if needed for scheduling | Arrange the session and withdrawal | Directly identifiable | Delete after [DATE/SESSION] |
| Participant code | Link a withdrawal request before anonymisation | Pseudonymous | Destroy the code key on [WITHDRAWAL DATE] |
| Task success, time, errors, retries and corrections | Usability evaluation | Coded | Delete coded data on [DATE]; retain anonymous aggregates |
| Text prompts and AI outputs using standard materials | Text-model workflow evaluation | Coded/non-personal by design | Delete coded data on [DATE] |
| Speech transcript, expected/predicted intent and action | Audio workflow evaluation | Potentially personal if unexpected content is spoken | Review/redact promptly; delete coded data on [DATE] |
| Raw microphone audio | Local transcription only | Potentially identifiable | Delete immediately; do not retain |
| Ratings and observation notes | Usability and trust analysis | Coded | Delete coded data on [DATE] |
| Anonymous quotations, if separately permitted | Illustrate findings | Anonymised after disclosure review | Retain in assessed report |

## 4. Data flow and security

1. Assign a participant code before the session.
2. Store signed forms separately from the worksheet and application results.
3. Run MealMatch locally. The `/transcribe-audio` endpoint writes a temporary
   upload only for inference and deletes it in a `finally` block.
4. Record only the fields in the approved worksheet.
5. Review free text immediately and redact accidental names or sensitive
   disclosures.
6. Store working files in an encrypted, password-protected folder on the
   institution-approved device or storage service. Do not use personal email,
   public links, GitHub or unapproved generative-AI services for participant
   data.
7. Share only anonymised summaries with assessors unless the approved process
   explicitly requires controlled access to coded data.
8. Destroy the participant-code key after the withdrawal deadline, then delete
   all remaining identifiable/coded working data on the approved deletion date.

If identifiable data would move between Singapore and the UK, stop and obtain
institutional advice before collection. Singapore requires comparable
protection for overseas transfers, and UK GDPR has separate international-
transfer rules. The simplest design is to keep identifiable data in the
approved Singapore storage location and put only genuinely anonymised,
aggregated findings in the report submitted to Goldsmiths.

## 5. Recommended participant number

Use a target of **10 completed participants**, with an acceptable range of
**8–12** for the main moderated formative study. This is a manageable final-year
project sample that can reveal repeated usability problems and produce useful
descriptive counts, medians and ranges across the integrated workflow. It is
not large enough for population estimates or inferential claims, and the report
must say that the sample was small and purposive.

Each participant should attempt the same core tasks. For the speech component,
10 participants completing 10 commands each produces approximately 100 real
command attempts, which is substantially stronger ecological evidence than a
single demonstration while remaining feasible to observe and verify. Include
both fixed commands and one or two naturally phrased commands per participant.

If recruitment is difficult, 6–8 well-documented sessions can still support a
formative usability study, but the limitation should be prominent. Recruiting
more than 12 is less valuable than collecting complete, consistent data and
showing a clear trace from findings to design changes and re-testing.

## 6. Analysis and reporting

Report:

- recruitment method, inclusion criteria, completed/withdrawn sessions and
  missing data;
- task success, partial success and failure counts;
- medians and ranges for completion time and ease ratings;
- text-output correctness, corrections and blinded usefulness ratings;
- speech transcription/intent/action success, retries and latency;
- qualitative themes supported by anonymous quotations where permitted;
- design changes made because of the evidence; and
- a short re-test of the most important changes, if time permits.

Do not call the sample representative, do not run significance tests merely to
make the study appear stronger, and do not combine repeated attempts as if they
came from independent participants. A transparent small study with frozen
tasks, complete records and evidence-driven iteration is academically stronger
than a larger but inconsistent convenience sample.

## 7. Documents required before recruitment

- approved ethics application and risk assessment;
- final Participant Information Sheet with the current Goldsmiths privacy
  notice appended in full;
- final consent form;
- recruitment message;
- standard task script and test materials;
- observer/data-capture worksheet;
- withdrawal and deletion procedure; and
- data breach or incident contact procedure supplied by the institutions.

## 8. Official references checked

- [Goldsmiths research governance, ethics and integrity](https://www.gold.ac.uk/research/governance/)
- [Goldsmiths Data Protection Policy](https://www.gold.ac.uk/media/docs/data-protection/Data-Protection-Policy.pdf)
- [UK ICO research provisions](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/the-research-provisions/)
- [UK ICO international-transfer guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/international-transfers/)
- [Singapore PDPC data-protection obligations](https://www.pdpc.gov.sg/overview-of-pdpa/the-legislation/personal-data-protection-act/data-protection-obligations)
- [Singapore PDPC guidance on photography, video and audio recordings](https://www.pdpc.gov.sg/-/media/files/pdpc/pdf-files/advisory-guidelines/ag-on-selected-topics/advisory-guidelines-on-the-pdpa-for-selected-topics-%28revised-may-2024%29.pdf)

These sources provide general institutional and regulatory guidance. The
programme and institutions must still confirm the applicable approval route,
controller, lawful basis, transfer arrangement and retention period for this
specific student project.
