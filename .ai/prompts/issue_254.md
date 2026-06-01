# Issue 254 Prompt

Fix DashboardViewModel unit tests that leak live ORIN patient-scope requests.
Inject `FakePatientScopeFetcher` in successful upload and dashboard-refresh test
fixtures that exercise patient-scope refreshes. Do not change production backend
configuration, ORIN labels, or patient-scope service behavior.
