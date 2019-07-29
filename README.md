# afl-sensitive
Sensitive and Collaborative Fuzzing with AFL

Directory Structure:

    ./                               # main code
        ./afl-*                      # implementation of different coverage metric based on AFL
            ./qemu_mode              # modified user-mode qemu for binary instrumentation
        ./afl-filter                 # instance that maintains a global seed queue for x-seeding
        ./Dockerfile                 # script to build Docker image
        ./start_afl.py               # script to start the whole fuzzing framework
        ./raise_state.py             # script to collect fuzzing stats
        ./data
            ./bins                   # binaries and initial seeds
            ./results                # detailed evaluation results
