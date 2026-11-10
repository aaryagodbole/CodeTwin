Files copied from the NameRTS replication package (https://github.com/ZJU-CTAG/NameRTS, Apache License 2.0,
see LICENSE-NameRTS): the ground truth (gt_*.json) and the published NameRTS selections (NameBDP_RTSTest_*.json)
for loguru (LOG), pvlib (PVL) and seaborn (SE). collect.py --pairs uses gt_<project>.json to choose the commit
pairs; analyze.py evaluates the published NameRTS selections on the same changes.
