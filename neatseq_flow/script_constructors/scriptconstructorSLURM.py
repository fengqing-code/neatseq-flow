import os, shutil, sys, re
import traceback
import datetime


from copy import *
from pprint import pprint as pp

__author__ = "Menachem Sklarz"
__version__ = "1.2.0"


from scriptconstructor import *

def get_script_exec_line():
    """ Return script to add to script execution function """
    

    return """\
jobid=$(sbatch $script_path | cut -d " " -f 4)

sed -i -e "s:$1$:$1\\t$jobid:" $run_index
"""


class ScriptConstructorSLURM(ScriptConstructor):

        
        
    def get_command(self):
        """ Returnn the command for executing the this script
        """
        
        qsub_line = ""
        qsub_line += "echo running " + self.name + " ':\\n------------------------------'\n"
        
        # slow_release_script_loc = os.sep.join([self.pipe_data["home_dir"],"utilities","qsub_scripts","run_jobs_slowly.pl"])

        if "slow_release" in self.params.keys():
            sys.exit("Slow release no longer supported. Use 'job_limit'")

        else:
            qsub_line += "{nsf_exec} {scripts_dir}{script_name}\n".format(scripts_dir = self.pipe_data["scripts_dir"], 
                                                                        script_name = self.script_name,
                                                                        nsf_exec = self.pipe_data["exec_script"])

        qsub_line += "\n\n"
        return qsub_line

        
#### Methods for adding lines:
        
        
        
    def get_kill_command(self):
    
        # TODO: somehow this has to be the numeric run-0time job id!
        return "# scancel JOB_ID \n" #{script_name}".format(script_name = self.script_id)
        
    def make_script_header(self):
        """ Make the first few lines for the scripts
            Is called for high level, low level and wrapper scripts
        """
        
        
        # qsub_header = "#!/bin/{shell}".format(shell=self.shell)   # Defintion of shell in args not abvailable for sbatch\n#$ -S /bin/%(shell)s" % {"shell": self.shell}
        # # Make hold_jids line only if there are jids (i.e. self.get_dependency_jid_list() != [])
        # if self.dependency_jid_list:
            # qsub_holdjids = "#$ -hold_jid %s " % self.dependency_jid_list
        # else:
            # qsub_holdjids = ""
        # qsub_name =    "#SBATCH --job-name %s " % (self.spec_qsub_name)
        # qsub_stderr =  "#SBATCH -e {stderr_dir}{name}.e%J".format(stderr_dir=self.pipe_data["stderr_dir"],name=self.spec_qsub_name)
        # qsub_stdout =  "#SBATCH -o {stdout_dir}{name}.o%J".format(stdout_dir=self.pipe_data["stdout_dir"],name=self.spec_qsub_name) 
        # if "queue" in self.params["qsub_params"]:
            # qsub_queue =   "#SBATCH --partition %s" % self.params["qsub_params"]["queue"]

            
        qsub_header = """\
#!/bin/{shell}
#SBATCH --job-name {jobname}
#SBATCH -e {stderr_dir}{jobname}.e%%J
#SBATCH -o {stdout_dir}{jobname}.o%%J
""".format(shell      = self.shell, \
           stderr_dir = self.pipe_data["stderr_dir"],
           stdout_dir = self.pipe_data["stdout_dir"],
           jobname    = self.script_id) 
        if "queue" in self.params["qsub_params"]:
            qsub_header +=   "#SBATCH --partition %s\n" % self.params["qsub_params"]["queue"]
        if self.dependency_jid_list:
            qsub_header += "#$ -hold_jid %s " % self.dependency_jid_list
            
        return qsub_header  
        #"\n".join([qsub_shell,
                            # qsub_name,
                            # qsub_stderr,
                            # qsub_stdout,
                            # qsub_holdjids]).replace("\n\n","\n") 
        
        
        

        
        
        
####----------------------------------------------------------------------------------

class HighScriptConstructorSLURM(ScriptConstructorSLURM,HighScriptConstructor):
    """
    """
    
        

    def get_depends_command(self, dependency_list):
        """
        """
        
        return "# scontrol bla bla bla... Find out how is done\n\n"#qalter \\\n\t-hold_jid %s \\\n\t%s\n\n" % (dependency_list, self.script_id)


        
    def make_script_header(self, **kwargs):
        """ Make the first few lines for the scripts
            Is called for high level, low level and wrapper scripts
        """

        general_header = super(HighScriptConstructorSLURM, self).make_script_header(**kwargs)

        only_low_lev_params  = ["-pe"]
        compulsory_high_lev_params = {"-V":""}

        if "queue" in self.params["qsub_params"]:
            general_header +=   "#SBATCH --partition %s" % self.params["qsub_params"]["queue"]

        # Create lines containing the qsub opts.
        for qsub_opt in self.params["qsub_params"]["opts"]:
            if qsub_opt in only_low_lev_params:
                continue
            general_header += "#SBATCH {key} {val}\n".format(key=qsub_opt, val=self.params["qsub_params"]["opts"][qsub_opt]) 


        # Adding 'compulsory_high_lev_params' to all high level scripts (This includes '-V'. Otherwise, if shell is bash, the SGE commands are not recognized)
        for qsub_opt in compulsory_high_lev_params:
            if qsub_opt not in self.params["qsub_params"]["opts"]:
                general_header += "#SBATCH {key} {val}\n".format(key = qsub_opt, 
                                                            val = compulsory_high_lev_params[qsub_opt]) 


        # Sometimes qsub_opts is empty and then there is an ugly empty line in the middle of the qsub definition. Removing the empty line with replace()
        return general_header + "\n\n"


    def write_child_command(self, script_path, script_id, qdel_line):
        """ Writing low level lines to high level script: job_limit loop, adding qdel line and qsub line
            spec_qsub_name is the qsub name without the run code (see caller)
        """
        
        
        script = ""

        
        if "job_limit" in self.pipe_data.keys():
            sys.exit("Job limit not supported yet for SLURM!")
            # script += """
# # Sleeping while jobs exceed limit
# perl -e 'use Env qw(USER); open(my $fh, "<", "%(limit_file)s"); ($l,$s) = <$fh>=~/limit=(\d+) sleep=(\d+)/; close($fh); while (scalar split("\\n",qx(%(qstat)s -u $USER)) > $l) {sleep $s; open(my $fh, "<", "%(limit_file)s"); ($l,$s) = <$fh>=~/limit=(\d+) sleep=(\d+)/} print 0; exit 0'

# """ % {"limit_file" : self.pipe_data["job_limit"],\
            # "qstat" : self.pipe_data["qsub_params"]["qstat_path"]}

            
#######            
        # Append the qsub command to the 2nd level script:
        # script_name = self.pipe_data["scripts_dir"] + ".".join([self.step_number,"_".join([self.step,self.name]),self.shell]) 
        script += """
# ---------------- Code for {script_id} ------------------
{qdel_line}
{nsf_exec} {script_id}

""".format(nsf_exec = self.pipe_data["exec_script"],
        qdel_line = qdel_line,
        script_name = script_path,
        script_id = script_id)

        
        self.filehandle.write(script)
                            
                            
                            
                            
####----------------------------------------------------------------------------------
    
class LowScriptConstructorSLURM(ScriptConstructorSLURM,LowScriptConstructor):
    """
    """

    def make_script_header(self, **kwargs):
        """ Make the first few lines for the scripts
            Is called for high level, low level and wrapper scripts
        """

        
        general_header = super(LowScriptConstructorSLURM, self).make_script_header(**kwargs)

        only_low_lev_params  = ["-pe"]
        compulsory_high_lev_params = {"-V":""}
        # special_opts = "-N -e -o -q -hold_jid".split(" ") + only_low_lev_params


        # Create lines containing the qsub opts.
        for qsub_opt in self.params["qsub_params"]["opts"]:
            general_header += "#SBATCH {key} {val}\n".format(key=qsub_opt, val=self.params["qsub_params"]["opts"][qsub_opt]) 
            
        if "queue" in self.params["qsub_params"]:
            general_header += "#SBATCH --partition %s\n" % self.params["qsub_params"]["queue"]
        # Adding node limitation to header, but only for low-level scripts
        if self.params["qsub_params"]["node"]:     # If not defined then this will be "None"
            # qsub_queue += "@%s" % self.params["qsub_params"]["node"]
            general_header += "#SBATCH --nodelist %s\n" % ",".join(self.params["qsub_params"]["node"])


        # Sometimes qsub_opts is empty and then there is an ugly empty line in the middle of the qsub definition. Removing the empty line with replace()
        return general_header + "\n\n"

        
        
####----------------------------------------------------------------------------------

class KillScriptConstructorSLURM(ScriptConstructorSLURM,KillScriptConstructor):


    pass