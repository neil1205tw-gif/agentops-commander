The documented Windows/no-make validation workflow fails when executed in the shown order, violating a stated acceptance criterion.

Review comment:

- [P2] Reset to the repository root before frontend commands — C:\side_workspace\AgentOps-Commander\README.md:45-45
  When users run this advertised no-`make` command block sequentially, the earlier `cd backend` remains in effect, so `cd frontend` tries to enter `backend/frontend` and fails. Consequently the frontend checks, backend image build, and formatting commands cannot be used as the documented equivalent of `make check`; use root-qualified paths or return to the root between sections.