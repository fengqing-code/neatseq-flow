# -*- coding: UTF-8 -*-
""" 
``UCSC_BW_wig``
----------------------------


:Authors: Menachem Sklarz
:Affiliation: Bioinformatics core facility
:Organization: National Institute of Biotechnology in the Negev, Ben Gurion University.


A module for creating wig and bigwig files using UCSC tools:

The module creates bigwig and wig files from the current active BedGraph file.


Requires
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* BedGraph file in the following slot:

    * ``sample_data[<sample>]["bdg"]``
    

Output
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

* Puts output sam files in the following slots:

    * self.sample_data[<sample>]["bw"]
    * self.sample_data[<sample>]["wig"]
    
Parameters that can be set
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. csv-table:: 
    :header: "Parameter", "Values", "Comments"
    :widths: 15, 10, 10

    "bedGraphToBigWig_params", "*e.g.* -blockSize=10 -itemsPerSlot=20", "Parameters to pass to ``bedGraphToBigWig``"
    "bigWigToWig_params", "*e.g.* -chrom X1 -start X2 -end X3", "Parameters to pass to ``bigWigToWig``"
    "script_path", "", "Path to dir where UCSC tools are located."
    "scope", "sample|project", "Where the 'bdg' is located"

    
.. note:: Set ``script_path`` to the path of the UCSC tools, not to a specific tool!!! If they are in the PATH, as when installing with CONDA, leave the ``script_path`` empty.
    Both ``bedGraphToBigWig`` and ``bigWigToWig`` will be executed. To set specific params, use ``bedGraphToBigWig_params`` and ``bigWigToWig_params``, respectively.

Lines for parameter file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    UCSCmap_bams:
        module:         UCSC_BW_wig
        base:           genCovBed_sam
        script_path:    /path/to/ucscTools/kentUtils/bin/
        genome:        /path/to/ref_genome.chrom.sizes
        bedGraphToBigWig_params:     -blockSize=10 -itemsPerSlot=20
        bigWigToWig_params:          -chrom X1 -start X2 -end X3

References
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Kent, W.J., Zweig, A.S., Barber, G., Hinrichs, A.S. and Karolchik, D., 2010. **BigWig and BigBed: enabling browsing of large distributed datasets**. *Bioinformatics*, 26(17), pp.2204-2207.
"""


import os
import sys
from neatseq_flow.PLC_step import Step,AssertionExcept


__author__ = "Menachem Sklarz"
__version__ = "1.6.0"


class Step_UCSC_BW_wig(Step):
    
    def step_specific_init(self):
        self.shell = "bash"      # Can be set to "bash" by inheriting instances

        if not "genome"  in self.params:
            raise AssertionExcept("You must pass a 'genome' parameter!")

        if self.params["script_path"]:
            self.params["script_path"] = self.params["script_path"].rstrip(os.sep) + os.sep
        else:
            self.params["script_path"] = ""

        if "scope" not in self.params:
            self.params["scope"] = "sample"

    def step_sample_initiation(self):
        """ A place to do initiation stages following setting of sample_data
        """

        if self.params["scope"] == "project":
            sample_list = ["project_data"]
        elif self.params["scope"] == "sample":
            sample_list = self.sample_data["samples"]
        else:
            raise AssertionExcept("'scope' must be either 'sample' or 'project'")

        for sample in sample_list:      # Getting list of samples out of samples_hash
            if "bdg" not in self.sample_data[sample]:
                raise AssertionExcept("'bdg' does not exist!")

    def create_spec_wrapping_up_script(self):
        """ Add stuff to check and agglomerate the output data
        """
        pass
        
    
    def build_scripts(self):
        """ This is the actual script building function
            Most, if not all, editing should be done here 
            HOWEVER, DON'T FORGET TO CHANGE THE CLASS NAME AND THE FILENAME!
        """
        if self.params["scope"] == "project":
            sample_list = ["project_data"]
        elif self.params["scope"] == "sample":
            sample_list = self.sample_data["samples"]
        else:
            raise AssertionExcept("'scope' must be either 'sample' or 'project'")

        for sample in sample_list:      # Getting list of samples out of samples_hash

            # Make a dir for the current sample:
            sample_dir = self.make_folder_for_sample(sample)

            # Name of specific script:
            self.spec_script_name = self.set_spec_script_name(sample)
            self.script = ""

            # This line should be left before every new script. It sees to local issues.
            # Use the dir it returns as the base_dir for this step.
            use_dir = self.local_start(sample_dir)
            
            # Define input and output files
            input_file = self.sample_data[sample]["bdg"]
            
            output_file_bw  = "%s.bw"  % os.path.basename(input_file)
            output_file_wig = "%s.wig" % os.path.basename(input_file)
            
            # Creating bedGraphToBigWig script:
            self.script += "# Converting bdg to bigWig:\n\n"
            # Adding env, if it exists:
            if "env" in list(self.params.keys()):         # Add optional environmental variables.
                script_const += "env %s \\\n\t" % self.params["env"]
            # Adding bedGraphToBigWig executable
            self.script += "%sbedGraphToBigWig \\\n\t" % (self.params["script_path"])
            # Adding parameters, if the exist
            if "bedGraphToBigWig_params" in self.params and self.params["bedGraphToBigWig_params"]:
                self.script += "%s \\\n\t" % self.params["bedGraphToBigWig_params"]
            # Adding input, genome and output files:
            self.script += "%s \\\n\t" % (input_file)
            self.script += "%s \\\n\t" % self.params["genome"]
            self.script += "%s\n\n" % (use_dir + output_file_bw)
            
            # Creating bigWigToWig script:
            self.script += "# Converting bigWig to wig:\n\n"
            self.script += "%sbigWigToWig \\\n\t" % (self.params["script_path"])
            if "bigWigToWig_params" in self.params and self.params["bigWigToWig_params"]:
                self.script += "%s \\\n\t" % self.params["bigWigToWig_params"]
            self.script += "%s \\\n\t" % (use_dir + output_file_bw)
            self.script += "%s\n\n" % (use_dir + output_file_wig)

            self.sample_data[sample]["bw"]  = "%s%s" % (sample_dir, output_file_bw)
            self.sample_data[sample]["wig"] = "%s%s" % (sample_dir, output_file_wig)
    
            # Stamping output files:
            self.stamp_file(self.sample_data[sample]["bw"])
            self.stamp_file(self.sample_data[sample]["wig"])
        
            # Move all files from temporary local dir to permanent base_dir
            self.local_finish(use_dir,sample_dir)
            self.create_low_level_script()
                    
        
