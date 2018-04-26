import os, shutil, sys, re
import traceback
import datetime


from copy import *
from pprint import pprint as pp

__author__ = "Menachem Sklarz"
__version__ = "1.2.0"


from scriptconstructor import *


class ScriptConstructorLocal(ScriptConstructor):

    @classmethod
    def get_exec_script(cls, pipe_data):
        """ Not used for SGE. Returning None"""

        script = super(ScriptConstructorLocal, cls).get_exec_script(pipe_data)

        script += """\
# locksed "s:\($1\).*$:\\1\\trunning:" $run_index

iscsh=$(grep "csh" <<< $script_path)
if [ -z $iscsh ]; then
    sh $script_path &
else
    csh $script_path &
fi

gpid=$(ps -o pgid= $! | grep -o '[0-9]*')
locksed "s:$qsubname.*$:&\t$gpid:" $run_index


"""
        return script

        
    def get_command(self):
        """ Returnn the command for executing the this script
        """
        
        script = ""


        if "slow_release" in self.params.keys():
            sys.exit("Slow release no longer supported. Use 'job_limit'")

        else:
            script += """\
sh {nsf_exec} \\
    {script_id} \\
    1> {stdout} \\
    2> {stderr} & \n\n""".format(script_id = self.script_id,
                          nsf_exec = self.pipe_data["exec_script"],
                          stderr = "{dir}{id}.e".format(dir=self.pipe_data["stderr_dir"], id=self.script_id),
                          stdout = "{dir}{id}.o".format(dir=self.pipe_data["stdout_dir"], id=self.script_id))


        return script

        
#### Methods for adding lines:
        
                
        
        
###################################################
        
        
    def get_kill_command(self):
        """
        """
        pass
        # TODO: somehow this has to be the numeric run-0time job id!
        # return "# scancel JOB_ID \n" #{script_name}".format(script_name = self.script_id)
        
    def get_script_header(self):
        """ Make the first few lines for the scripts
            Is called for high level, low level and wrapper scripts
        """

            
        qsub_header = """#!/bin/{shell}\n""".format(shell      = self.shell)
        
        if self.dependency_jid_list:
            qsub_header += "#$ -hold_jid %s " % self.dependency_jid_list
            
        return qsub_header  

# ----------------------------------------------------------------------------------
# HighScriptConstructorLocal defintion
# ----------------------------------------------------------------------------------


class HighScriptConstructorLocal(ScriptConstructorLocal,HighScriptConstructor):
    """
    """


    def get_depends_command(self, dependency_list):
        """
        """
        
        return ""
        # scontrol bla bla bla... Find out how is done\n\n"#qalter \\\n\t-hold_jid %s \\\n\t%s\n\n" % (dependency_list, self.script_id)


        
    def get_script_header(self, **kwargs):
        """ Make the first few lines for the scripts
            Is called for high level, low level and wrapper scripts
        """

        general_header = super(HighScriptConstructorLocal, self).get_script_header(**kwargs)

        return general_header + "\n\n"

    def get_command(self):
        """ Writing low level lines to high level script: job_limit loop, adding qdel line and qsub line
            spec_qsub_name is the qsub name without the run code (see caller)
        """
        
        # if "job_limit" in self.pipe_data.keys():
        #     sys.exit("Job limit not supported yet for Local!")


        command = super(HighScriptConstructorLocal, self).get_command()

        

        # TODO: Add output from stdout and stderr

        script = """
# ---------------- Code for {script_id} ------------------
echo running {script_id}
{command}

sleep {sleep_time}

""".format(script_id=self.script_id,
           command=command,
           sleep_time=self.pipe_data["Default_wait"])

        return script

    def get_child_command(self, script_obj):
        """ Writing low level lines to high level script: job_limit loop, adding qdel line and qsub line
            spec_qsub_name is the qsub name without the run code (see caller)
        """

        job_limit = ""

        if "job_limit" in self.pipe_data.keys():
            # sys.exit("Job limit not supported yet for Local!")

            job_limit = """\
# Sleeping while jobs exceed limit
while : ; do numrun=$(egrep -c "^\w" {run_index}); maxrun=$(sed -ne "s/limit=\([0-9]*\).*/\\1/p" {limit_file}); sleeptime=$(sed -ne "s/.*sleep=\([0-9]*\).*/\\1/p" {limit_file}); [[ $numrun -ge $maxrun ]] || break; sleep $sleeptime; done
""".format(limit_file=self.pipe_data["job_limit"],
           run_index=self.pipe_data["run_index"])

        script = """
# ---------------- Code for {script_id} ------------------
{job_limit}

{child_cmd}

sleep {sleep_time}
""".format(script_id=script_obj.script_id,
           child_cmd=script_obj.get_command(),
           sleep_time=self.pipe_data["Default_wait"],
           # run_index=self.pipe_data["run_index"],
           job_limit=job_limit)

        return script

    def get_script_postamble(self):
        """ Local script postamble is same as general postamble with addition of sed command to mark as finished in run_index
        """

        # Write the kill command to the kill script
        try:
            self.kill_obj.write_kill_cmd(self.script_id)
        except AttributeError:
            pass
        # Get general postamble
        postamble = super(HighScriptConstructorLocal, self).get_script_postamble()

        # Add sed command:
        script = """\
{postamble}

wait 

# Setting script as done in run index:
# Using locksed provided in helper functions
locksed  "s:^\({script_id}\).*:# \\1\\tdone:" {run_index}

""".format(\
            postamble = postamble,
            run_index = self.pipe_data["run_index"],
            script_id = self.script_id)
        
        return script

# ----------------------------------------------------------------------------------
# LowScriptConstructorLocal defintion
# ----------------------------------------------------------------------------------


class LowScriptConstructorLocal(ScriptConstructorLocal, LowScriptConstructor):
    """
    """

    def get_script_header(self, **kwargs):
        """ Make the first few lines for the scripts
            Is called for high level, low level and wrapper scripts
        """

        
        general_header = super(LowScriptConstructorLocal, self).get_script_header(**kwargs)

        return general_header + "\n\n"

    def write_script(self,
                     script,
                     dependency_jid_list,
                     stamped_files,
                     **kwargs):
        """ Assembles the scripts to writes to file
        """

        if "level" not in kwargs:
            kwargs["level"] = "low"

        locksed_cmd = """\
# Adding subprocess pid to run_index
locksed  "s:^{script_id}.*:&\\t$!:" {run_index}
""".format(run_index=self.pipe_data["run_index"],
           script_id=self.script_id)

        final_locksed_cmd = """\

# Setting script as done in run index:
# Using locksed provided in helper functions 
locksed  "s:^\({script_id}\).*:# \\1\\tdone:" {run_index}

""".format(run_index = self.pipe_data["run_index"],
           script_id = self.script_id)


        script = "\n".join([
            self.get_script_preamble(dependency_jid_list),
            self.get_trap_line(),
            self.get_log_lines(state="Started"),
            self.get_activate_lines(type="activate"),
            self.get_set_options_line(type="set"),
            # THE SCRIPT!!!!
            script,
            locksed_cmd,
            self.get_stamped_file_register(stamped_files),
            self.get_set_options_line(type="unset"),
            self.get_activate_lines(type="deactivate"),
            self.get_kill_line(state="Stop"),
            self.get_log_lines(state="Finished"),
            final_locksed_cmd])

        self.write_command(script)

        # Write the kill command to the kill script
        try:
            self.kill_obj.write_kill_cmd(self.script_id)
        except AttributeError:
            pass

# ----------------------------------------------------------------------------------
# KillScriptConstructorLocal defintion
# ----------------------------------------------------------------------------------


class KillScriptConstructorLocal(ScriptConstructorLocal,KillScriptConstructor):


    def write_kill_cmd(self, script_id):
        """

        :return:
        """

        script = """\
line2kill=$(grep '^{script_id}' {run_index} | cut -f 3-)
line2kill=(${{line2kill//,/ }})
for item1 in "${{line2kill[@]}}"; do 
    echo $item1
    kill -TERM $item
done

""".format(run_index = self.pipe_data["run_index"],
           script_id=script_id)

        self.filehandle.write(script)



