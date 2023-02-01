source benchmarks/train_loop.sh
ALGOS="ppo"
ENVS="HalfCheetahBulletEnv-v0 AntBulletEnv-v0 Walker2DBulletEnv-v0 HopperBulletEnv-v0"
train_loop $ALGOS "$ENVS" | xargs -I CMD --max_procs=3 bash -c CMD