#!/usr/bin/env bash
set -e

cd /home/ares/Zoids/Character_Sheet_app
source .venv/bin/activate
trap deactivate EXIT

flet build linux

deactivate
rsync -av /home/ares/Zoids/Character_Sheet_app/build/linux/ /home/ares/Zoids/RPG_Tools/Character_Sheet/
trap - EXIT

cd /home/ares/Zoids/Zoids_Encounter_Tracker
source .venv/bin/activate
trap deactivate EXIT

flet build linux

deactivate
rsync -av /home/ares/Zoids/Zoids_Encounter_Tracker/build/linux/ /home/ares/Zoids/RPG_Tools/Encounter_Tracker/
trap - EXIT

