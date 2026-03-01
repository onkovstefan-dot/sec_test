I want to ....
- ....
- ....

Check and create plan for ai agents in docs/standards with extra index _date


- Extract/move/refactor common logic depending only on pure python functionalities into utils folder
- Extract/move/refactor common business logic depending on db models into modules folder
- Extract/move/refactor one time manual or background jobs into support folder
- Imports only on top of the file, not in methods or classes
- Keep root as clean as possible 
- Check for files not meant to commit to GitHub
- Check if our test coverage is good
- Consider security practices for full stack apps. Implement defensive mechanisms and data sanitization on all layers - frontend, backend and db
- Consider data privacy and protection  - sanitze and ananonymize user data. Implement retention mechanism and expiration for personal data
- Create summary and suggest optmizations - new frameworks, libraries, packages or tools; performance improvements; syntax improvements; others


Create a plan in docs/standards
make into separate, consequtive, fresh sessions with ai agents
add mentions and references of README.md to ensure constext and robustness of the plan
consider intermidiete instructions and steps to ensure robust plan execution and context handling between fresh agent sessions
If needed keep notes in folder tmp and let all agents from different session use the notes. I will not verify anything between sessions. I will do one final commit and manual run of all pytests at the end
make separate file with ready copy paste intructions per session to feed to the agent. make the file name the same as the plan with extra index _agent_instructions
At he end, ensure clean code and structure. No dead or unused code is left. No temp files. If needed add steps and checks per session 




Create only plan with generic steps. Do not refer to the current implementation in the generic plan. Do not edit any files, just make generic plan that I can execute repeatedly over time