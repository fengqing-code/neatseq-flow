import os
import shutil
import sys
import re
import traceback
import datetime

from copy import *
from pprint import pprint as pp

__author__ = "Menachem Sklarz"
__version__ = "1.6.0"


from .scriptconstructor import *


class ScriptConstructorSGE(ScriptConstructor):
    """ Class for implementing ScriptConstructor class for SGE executor
    """

    @classmethod
    def get_helper_script(cls, pipe_data):
        """ Returns the code for the helper script
        """
        script = super(ScriptConstructorSGE, cls).get_helper_script(pipe_data)

        # Add locksed command. For SGE, just remove
        script = re.sub("## locksed command entry point", r"", script)

        # Add maxvmem calculation command:
        # $6 is the job_id!

        maxvmem_cmd = """
        if [ ! $jobid == 'ND' ]; then
            maxvmem=$({qstat_path} -j $jobid | grep maxvmem | cut -d = -f 6);
        else
            maxvmem="NA";
        fi""".format(qstat_path=pipe_data["qsub_params"]["qstat_path"]   # If os=linux, no need to escape
                                    if(os.sep == '/')
                                    else re.escape(pipe_data["qsub_params"]["qstat_path"])) # if os=windows, have to escape '\' in path!

        script = re.sub("## maxvmem calc entry point", maxvmem_cmd, script)

        # Add job_limit function:
        if "job_limit" in pipe_data:
            script += """\
job_limit={job_limit}

wait_limit() {{
    while : ; do 
        numrun=$({qstat} -u $USER | wc -l ); 
        maxrun=$(sed -ne "s/limit=\([0-9]*\).*/\\1/p" $job_limit); 
        sleeptime=$(sed -ne "s/.*sleep=\([0-9]*\).*/\\1/p" $job_limit); 
        [[ $numrun -ge $maxrun ]] || break; 
        sleep $sleeptime; 
    done
}}
""".format(job_limit=pipe_data["job_limit"],
           qstat=pipe_data["qsub_params"]["qstat_path"])

        return script

    @classmethod
    def get_exec_script(cls, pipe_data):
        """ Not used for SGE. Returning None"""

        return None

    @classmethod
    def get_utilities_script(cls, pipe_data):

        util_script = super(ScriptConstructorSGE, cls).get_utilities_script(pipe_data)

        # # Steps:
        # 1. Find failed steps in log file
        # 2. Find downstream steps in depend_file
        # 3. Get qsub commands from main script
        # 4. Execute the qsub command

        recover_script = util_script + """
# Recover a failed execution
function recover_run {{
    cat {log_file} \\
        | awk '{{  if(NR<=9) {{next}}; 
                    if($3=="Started" && $11 ~ "OK") {{jobs[$6]=$5;}}
                    if($3=="Finished" && $11 ~ "OK") {{delete jobs[$6]}}
                }}
                END {{
                    for (key in jobs) {{ 
                        print jobs[key]
                    }} 
                
                }}'  \\
        | while read step; do \\
            echo $step; \\
            grep $step {depend_file} | cut -f2; 
          done \\
        | sort -u \\
        | while read step; do \\
            grep $step {main} | egrep -v "^#|^echo" | cut -f2 -d" ";
          done \\
        | sort -u \\
        | while read line; do \\
            echo $line;
            qsub $line; \\
          done
}}
        """.format(log_file=pipe_data["log_file"],
                   depend_file=pipe_data["dependency_index"],
                   main=pipe_data["scripts_dir"] + "00.workflow.commands.sh")

        return recover_script + """
# Show active jobs
function show_PL_jobs { 
    currid=$(tail -n1  logs/version_list.txt | xargs | cut -f1)
    qstat -j *$currid | grep -e job_number -e submission_time -e owner -e cwd -e job_name -e "jid_predecessor_list:" -e script_file -e ================
}

# Show tail of current log file
function tail_curr_log {
    if [ -z $1 ] 
    then
        n=5
    else
        n=$1
    fi
    
    currid=$(tail -n1  logs/version_list.txt | xargs | cut -f1)

    log_file="logs/log_$currid.txt"
    tail -n $n $log_file
}        

function kill_all_PL_jobs {
    currid=$(tail -n1  logs/version_list.txt | xargs | cut -f1)
    qstat -j *$currid \\
        | grep -e job_number \\
        | cut -f2 -d ":" \\
        | while read jid; \\
          do qdel $jid; \\
          done

}
"""

    def get_command(self):
        """ Return the command for executing this script
        """
        script = ""

        if "slow_release" in list(self.params.keys()):
            sys.exit("Slow release no longer supported. Use 'job_limit'")
        else:
            script = """\
qsub {script_path}
""".format(script_path = self.script_path)

        return script


    def get_kill_command(self):
    
        return "qdel {script_name}".format(script_name = self.script_id)
        
    def get_script_header(self):
        """ Make the first few lines for the scripts
            Is called for high level, low level and wrapper scripts
        """

        qsub_shell = "#!/bin/%(shell)s\n#$ -S /bin/%(shell)s" % {"shell": self.shell}
        # Make hold_jids line only if there are jids (i.e. self.get_dependency_jid_list() != [])
        if self.master.dependency_jid_list:
            # Old style: Full list of jids:
            # qsub_holdjids = "#$ -hold_jid %s " % ",".join(self.master.dependency_jid_list)
            # New style: Using globs:
            qsub_holdjids = "#$ -hold_jid {hold_jid_list}".format(
                hold_jid_list=",".join(['"%s"' % x for x in self.master.dependency_glob_jid_list]))
        else:
            qsub_holdjids = ""

        qsub_name =    "#$ -N %s " % (self.script_id)
        qsub_stderr =  "#$ -e %s" % self.pipe_data["stderr_dir"]
        qsub_stdout =  "#$ -o %s" % self.pipe_data["stdout_dir"]
        # qsub_queue =   "#$ -q %s" % self.params["qsub_params"]["queue"]

        script_header = "\n".join([qsub_shell,
                                   qsub_name,
                                   qsub_stderr,
                                   qsub_stdout,
                                   qsub_holdjids]).replace("\n\n","\n")
        return script_header

    def get_log_lines(self, state="Started", status="\033[0;32mOK\033[m"):
        """ Create logging lines. Added before and after script to return start and end times
                If bash, adding at beginning of script also lines for error trapping
        """

        log_cols_dict = {"type": state,
                     "step": self.step,
                     "stepname": self.name,
                     "stepID": self.script_id,
                     "qstat_path": self.pipe_data["qsub_params"]["qstat_path"],
                     "level": self.level,
                     "status": status,
                     "file": self.pipe_data["log_file"]}

        if self.shell == "csh":

                script = """
if ($?JOB_ID) then 
    # Adding line to log file:  Date    Step    Host
    echo `date '+%%d/%%m/%%Y %%H:%%M:%%S'`'\\t%(type)s\\t%(step)s\\t%(stepname)s\\t%(stepID)s\\t%(level)s\\t'$HOSTNAME'\\t'$JOB_ID'\\t'`%(qstat_path)s -j $JOB_ID | grep maxvmem | cut -d = -f 6`'\\t%(status)s' >> %(file)s
else
    echo `date '+%%d/%%m/%%Y %%H:%%M:%%S'`'\\t%(type)s\\t%(step)s\\t%(stepname)s\\t%(stepID)s\\t%(level)s\\t'$HOSTNAME'\\t'$$'\\t-\\t%(status)s' >> %(file)s
endif
####
""" % log_cols_dict

        elif self.shell == "bash":

            script = """
# Adding line to log file
log_echo {step} {stepname} {stepID} {level} $HOSTNAME $JOB_ID {type}

""".format(**log_cols_dict)

        else:
            script = ""

            if self.pipe_data["verbose"]:
                sys.stderr.write("shell not recognized. Not creating log writing lines in scripts.\n")

        return script



# ----------------------------------------------------------------------------------
# HighScriptConstructorSGE definition
# ----------------------------------------------------------------------------------


class HighScriptConstructorSGE(ScriptConstructorSGE,HighScriptConstructor):
    """ A class for creating the high-level script for NeatSeq-Flow when Executor is SGE
    """

    def get_depends_command(self):
        """
        """

        # Old method:
        # return "qalter \\\n\t-hold_jid %s \\\n\t%s\n\n" % (dependency_list, self.script_id)
        # New methods wirh glob:

        return "qalter \\\n\t-hold_jid {glob_jid_list} \\\n\t{script_id}\n\n".format(
            # Comma separated list of double-quote enclosed glob jids:
            glob_jid_list=",".join(['"%s"' % x for x in self.master.dependency_glob_jid_list]),
            script_id=self.script_id)

    def get_script_header(self, **kwargs):
        """ Make the first few lines for the scripts
            Is called for high level, low level and wrapper scripts
        """

        general_header = super(HighScriptConstructorSGE, self).get_script_header(**kwargs)

        only_low_lev_params  = ["-pe"]
        compulsory_high_lev_params = {"-V":""}

        qsub_queue =   "#$ -q %s" % self.params["qsub_params"]["queue"]

        # Create lines containing the qsub opts.
        qsub_opts = ""
        for qsub_opt in self.params["qsub_params"]["opts"]:
            if qsub_opt in only_low_lev_params:
                continue
            qsub_opts += "#$ {key} {val}\n".format(key=qsub_opt, val=self.params["qsub_params"]["opts"][qsub_opt]) 

        # Adding 'compulsory_high_lev_params' to all high level scripts (This includes '-V'. Otherwise,
        # if shell is bash, the SGE commands are not recognized)
        for qsub_opt in compulsory_high_lev_params:
            if qsub_opt not in self.params["qsub_params"]["opts"]:
                qsub_opts += "#$ {key} {val}\n".format(key=qsub_opt, 
                                                val=compulsory_high_lev_params[qsub_opt]) 

        # Sometimes qsub_opts is empty and then there is an ugly empty line in the middle of the qsub definition.
        # Removing the empty line with replace()
        return "\n".join([general_header,
                            qsub_queue,
                            qsub_opts]).replace("\n\n","\n") + "\n\n"

    def get_command(self):
        """ Writing low level lines to high level script: job_limit loop, adding qdel line and qsub line
            spec_qsub_name is the qsub name without the run code (see caller)
        """

        command = super(HighScriptConstructorSGE, self).get_command()

        job_limit = ""

        if "job_limit" in list(self.pipe_data.keys()):
            job_limit = """
# Sleeping while jobs exceed limit
wait_limit
"""
        # TODO: Add output from stdout and stderr

        script = """
# ---------------- Code for {script_id} ------------------
{job_limit}
echo running {script_id}
{command}

""".format(script_id=self.script_id,
           job_limit=job_limit,
           command=command)

        return script

    def get_child_command(self, script_obj):
        """ Writing low level lines to high level script: job_limit loop, adding qdel line and qsub line
            spec_qsub_name is the qsub name without the run code (see caller)
        """

        job_limit = ""

        if "job_limit" in list(self.pipe_data.keys()):
            job_limit = """
# Sleeping while jobs exceed limit
wait_limit
"""

        script = """
# ---------------- Code for {script_id} ------------------
{job_limit}
echo '{qdel_line}' >> {step_kill_file}
# Adding qsub command:
qsub {script_name}

""".format(qdel_line = script_obj.get_kill_command(),
           job_limit=job_limit,
           script_name = script_obj.script_path,
           script_id = script_obj.script_id,
           step_kill_file = self.params["kill_script_path"])

        return script

    def get_script_postamble(self):
                            
        # Get general postamble
        postamble = super(HighScriptConstructorSGE, self).get_script_postamble()

        script = """\
{postamble}

csh {depends_script_name}

""".format(postamble = postamble,
           run_index = self.pipe_data["run_index"],
           depends_script_name = self.pipe_data["depends_script_name"])

        return script

    def main_script_kill_commands(self, kill_script_filename_main):

        f = open(kill_script_filename_main, 'r')
        kill_file = f.read()
        f.close()

        kill_file = re.sub("# entry_point",
                           "# entry_point\n{kill_cmd}".format(kill_cmd=self.get_kill_command()),
                           kill_file)

        f = open(kill_script_filename_main, 'w')
        f.write(kill_file)
        f.close()


# ----------------------------------------------------------------------------------
# LowScriptConstructorSGE definition
# ----------------------------------------------------------------------------------


class LowScriptConstructorSGE(ScriptConstructorSGE,LowScriptConstructor):
    """
    """

    def get_script_header(self, **kwargs):
        """ Make the first few lines for the scripts
            Is called for high level, low level and wrapper scripts
        """

        general_header = super(LowScriptConstructorSGE, self).get_script_header(**kwargs)

        only_low_lev_params  = ["-pe"]
        compulsory_high_lev_params = {"-V":""}

        # Create lines containing the qsub opts.
        qsub_opts = ""
        for qsub_opt in self.params["qsub_params"]["opts"]:
            qsub_opts += "#$ {key} {val}\n".format(key=qsub_opt, val=self.params["qsub_params"]["opts"][qsub_opt]) 

        qsub_queue =   "#$ -q %s" % self.params["qsub_params"]["queue"]
        # Adding node limitation to header, but only for low-level scripts
        if self.params["qsub_params"]["node"]:     # If not defined then this will be "None"
            # Perform two joins:
            #   1. For each node, join it to the queue name with '@' (e.g. 'bio.q@sge100')
            #   2. Comma-join all nodes to one list (e.g. 'bio.q@sge100,bio.q@sge102')
            qsub_queue = ",".join(["@".join([self.params["qsub_params"]["queue"],item]) for item in self.params["qsub_params"]["node"]])
            # qsub_queue += "@%s" % self.params["qsub_params"]["node"]
            qsub_queue = "#$ -q %s" % qsub_queue

        # Sometimes qsub_opts is empty and then there is an ugly empty line in the middle of the qsub definition.
        # Removing the empty line with replace()
        return "\n".join([general_header,
                          qsub_queue,
                          qsub_opts]).replace("\n\n", "\n") + "\n\n"

# ----------------------------------------------------------------------------------
# KillScriptConstructorSGE definition
# ----------------------------------------------------------------------------------


class KillScriptConstructorSGE(ScriptConstructorSGE,KillScriptConstructor):

    @classmethod
    def get_main_preamble(cls, *args):
        """ Return main kill-script preamble"""
        return """\
#!/bin/bash

# Remove high level scripts:
# entry_point

"""

    @classmethod
    def get_main_postamble(cls, *args):
        """ Return main kill-script postamble"""

        return ""

