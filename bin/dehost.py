#!/usr/bin/env python3

import argparse
import csv
import pysam
import os
import subprocess

from collections import defaultdict
from pathlib import Path

#读取contig_ID并且存为集合
with open("../ref_ID/ID.txt", "r") as f:
    content = f.read()

lines = [line.split(" ") for line in content.split("\n")]
contig = []
for line in lines:
    contig += line
contig_ID = contig

def init_parser():
    '''
    Parser Arguments to pass to script from CL
    '''

    parser = argparse.ArgumentParser()
    parser.add_argument('-f', '--file', required=True, help='Composite Reference BAM file of mapped reads')
    #parser.add_argument('-k', '--keep_id', required=False, type=set, help='Reference ID of genome to keep. Default: MN908947.3')
    parser.add_argument('-q', '--keep_minimum_quality', required=False, type=int, default=60, help='Minimum quality of the reads to keep')
    parser.add_argument('-Q', '--remove_minimum_quality', required=False, type=int, default=0, help='Minimum quality of the reads to be included in removal')
    parser.add_argument('-o', '--output', required=False, default='out.bam', help='Output BAM name')
    parser.add_argument('-R', '--revision', required=False, default='NA', help='Pass a pipeline commit hash to keep track of what version was ran')

    return parser


def get_reads_to_remove(bamfile_path, contig_ID, input_mapping_quality, reads_to_remove=set(), count=0):

    bamfile = pysam.AlignmentFile(bamfile_path, "rb")

    for read in bamfile.fetch():
        if read.reference_name != contig_ID and read.mapping_quality >= input_mapping_quality:
            reads_to_remove.add(read.query_name)
            count += 1
    bamfile.close()

    return reads_to_remove, count


def read_pair_generator(bam, region_string=None):
    """
    Generate read pairs for a SAM or BAM file or within a region string of said file.
    Reads are added to read_dict until a pair is found.
    """
    read_dict = defaultdict(lambda: [None, None])
    for read in bam.fetch(region=region_string):
        if not read.is_proper_pair or read.is_secondary or read.is_supplementary:
            continue

        qname = read.query_name
        if qname not in read_dict:
            if read.is_read1:
                read_dict[qname][0] = read
            else:
                read_dict[qname][1] = read
        else:
            if read.is_read1:
                yield read, read_dict[qname][1]
            else:
                yield read_dict[qname][0], read

            del read_dict[qname]


def remove_host_reads(bamfile_in, input_mapping_quality, remove_reads_set, reads_found=[], human_count=0, poor_quality_count=0):

    bamfile = pysam.AlignmentFile(bamfile_in, "rb")
    header = bamfile.header

    for read_1, read_2 in read_pair_generator(bamfile):
        if read_1 is None or read_2 is None:
            continue

        if read_1.query_name in remove_reads_set:
            human_count += 2
            continue

        elif read_1.mapping_quality >= input_mapping_quality and read_2.mapping_quality >= input_mapping_quality:
            reads_found.append(read_1)
            reads_found.append(read_2)

        else:
            poor_quality_count += 2

    bamfile.close()

    return reads_found, human_count, poor_quality_count, header


def generate_dehosted_output(reads_found, keep_header, bamfile_out):
    with pysam.AlignmentFile(bamfile_out, "w", header=keep_header) as outfile:
        for read in reads_found:
            outfile.write(read)


def main():
    parser = init_parser()
    args = parser.parse_args()

    sample_name = os.path.splitext(Path(args.file).stem)[0]

    remove_reads_set, human_read_count = get_reads_to_remove(args.file, args.remove_minimum_quality, args.keep_id)

    read_list, human_filtered_count, poor_quality_count, header = remove_host_reads(args.file, args.keep_minimum_quality, remove_reads_set)

    generate_dehosted_output(read_list, header, args.output)

    if len(read_list) == 0:
        percentage_kept = 0
    else:
        percentage_kept = len(read_list)/(human_filtered_count + poor_quality_count + len(read_list)) * 100

    line = {    'sample' : sample_name,
                'human_reads_filtered' : human_filtered_count, 
                'poor_quality_reads_filtered' : poor_quality_count,
                'paired_reads_kept' : len(read_list),
                'percentage_kept' : "{:.2f}".format(percentage_kept),
                'github_commit' : args.revision}

    with open('{}_stats.csv'.format(sample_name), 'w') as csvfile:
        header = line.keys()
        writer = csv.DictWriter(csvfile, fieldnames=header)
        writer.writeheader()
        writer.writerow(line)


if __name__ == "__main__":
    main()
