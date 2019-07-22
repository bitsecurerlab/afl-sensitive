FROM ubuntu


RUN apt-get update
RUN apt-get install -y unzip
RUN apt-get install -y python-dev 
RUN apt-get install -y libglib2.0-dev 
RUN apt-get install -y libpcap0.8-dev
RUN apt-get install -y sudo


RUN groupadd --system fuzz && useradd --create-home --shell /bin/bash --gid fuzz --system --groups sudo fuzz
RUN echo 'fuzz:fuzz' | chpasswd

WORKDIR /home/fuzz

ADD ./pip.py ./
RUN python pip.py
RUN rm pip.py


RUN mkdir /home/vagrant
RUN mkdir /home/vagrant/testcases







ADD ./start_afl.py ./start_afl.py
ADD ./raise_stats.py ./raise_stats.py
ADD ./input0 /home/vagrant/testcases


RUN chown fuzz:fuzz ./*.py
RUN chmod u+x ./*.py
#RUN chmod +s ./start_afl.py



ADD ./afl-filter ./afl-filter
ADD ./afl-bc ./afl-bc
ADD ./afl-ma ./afl-ma
ADD ./afl-ct ./afl-ct
ADD ./afl-n2 ./afl-n2
ADD ./afl-n4 ./afl-n4
ADD ./afl-n8 ./afl-n8

RUN rm -r ./afl-bc/qemu_mode/*
RUN rm -r ./afl-ma/qemu_mode/*
RUN rm -r ./afl-ct/qemu_mode/*
RUN rm -r ./afl-n2/qemu_mode/*
RUN rm -r ./afl-n4/qemu_mode/*
RUN rm -r ./afl-n8/qemu_mode/*

RUN chown -R fuzz:fuzz /home/fuzz
RUN chown -R fuzz:fuzz /home/vagrant

USER fuzz







