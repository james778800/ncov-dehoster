process generateCompositeReference {

    label 'smallcpu'

    input:
    path(human_ref)
    path(viral_ref)

    output:
    file("composite_reference.fa")

    script:
    """
    cat $human_ref $viral_ref > composite_reference.fa
    """
}


process grabCompositeIndex {

    label 'smallcpu'

    input:
    path(index_folder)

    output:
    file("*.fa*")

    script:
    """
    ln -sf $index_folder/*.fa* ./
    """
}

process indexCompositeReference {
    publishDir "${params.outdir}/humanBWAIndex", pattern: "*.fa*", mode: "symlink"

    label 'bwa_composite_index'

    input:
    path(composite_ref)

    output:
    file("*.fa*")

    script:
    """
    bwa index -a bwtsw $composite_ref
    """
}

process mapToCompositeIndex {

    publishDir "${params.outdir}/compositeMAPs", pattern: "${sampleName}.*", mode: "copy"

    label 'bwa_mem'

    input:
    tuple(sampleName, path(forward), path(reverse), path(composite_reference))
    path(indexed_reference)

    output:
    tuple sampleName, path("${sampleName}.sorted.bam"), emit: bam
    path("${sampleName}.flagstats.txt")

    script:
    """
    bwa mem -t ${params.illumina_threads} ${composite_reference} ${forward} ${reverse} | samtools sort --threads ${params.illumina_threads} -T "temp" -O BAM -o ${sampleName}.sorted.bam
    samtools flagstat ${sampleName}.sorted.bam > ${sampleName}.flagstats.txt
    """
}


process dehostBamFiles {

    publishDir "${params.outdir}/dehostedBAMs", pattern: "${sampleName}.dehosted.bam", mode: "copy"

    label 'mediumcpu'

    input:
    tuple(sampleName, path(composite_bam))

    output:
    tuple sampleName, path("${sampleName}.dehosted.bam"), emit: bam
    path "${sampleName}*.csv", emit: csv

    script:

    def rev = workflow.commitId ?: workflow.revision ?: workflow.scriptId

    """
    samtools index ${composite_bam}
    dehost.py --file ${composite_bam} \
    --keep_id ${params.covid_ref_id} \
    -q ${params.keep_min_map_quality} \
    -Q ${params.remove_min_map_quality} \
    -o ${sampleName}.dehosted.bam \
    -R ${rev} 
    """
}

process generateDehostedReads {

    publishDir "${params.outdir}/dehosted_fastqs", pattern: "${sampleName}-dehosted_R*", mode: "copy"

    label 'mediumcpu'

    input:
    tuple(sampleName, path(dehosted_bam))

    output:
    path("${sampleName}-dehosted_R*")

    script:
    """
    samtools fastq -1 ${sampleName}-dehosted_R1.fastq.gz -2 ${sampleName}-dehosted_R2.fastq.gz ${dehosted_bam}
    """
}

process combineCSVs {

    publishDir "${params.outdir}", pattern: "removal_summary.csv", mode: "copy"

    label 'smallcpu'

    input:
    path(csvs)

    output:
    path("removal_summary.csv")

    script:
    """
    csvtk concat *_stats.csv > removal_summary.csv
    """
}
