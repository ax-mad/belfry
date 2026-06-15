
# TEMPORARY LOCATION FOR ISSUES UNTIL A BETTER SYSTEM IS DESIGNED

## ISSUES

- [ ] **NEXT** DELETE REMINDERS: /reminders/delete/{id}

- [ ] SELF-DESTRUCTING REMINDERS AKA "time-to-live"
		Reminders should not stack up. Some reminders are only relevant in a small window.
		This feature depends on implementation of /reminders/delete endpoint

- [ ] WRITE A GO CLIENT WHICH CONNECTS TO BELFRY
		IMPLEMENT THESE DEPENDENCIES IN ORDER:
			- [ ] Logger
				- [ ] Add to https://github.com/ax-mad/pykit
			- [ ] Configurator
				- [ ] Add to pykit
				

- [ ] Implement auth by JWT token
		Allow family members to login and create reminders to their own channels, or my channel for that fact.

- [ ] Populate reminders by forwarding email to Belry
		Ability to extract attachments.


- [ ] Stick in Docker container

## UPKEEP

- write script for quickly running all services together in a single terminal
	- they must be considered as a single unit, cannot work with any of thejm missing
	- maybe write main.py to start 3 subprocesses with unified logs?

- clean this shit up
