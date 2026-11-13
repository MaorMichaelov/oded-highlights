# usage: trq.sh file1 file2 ...  (sequential worker)
cd /workspace/kick_clipper/streams/vod_137423561
for f in "$@"; do [ -f ${f%.wav}.done ] && continue; /workspace/venv_w/bin/python tr.py $f ${f%.wav}.txt 4 && echo DONE > ${f%.wav}.done; done
