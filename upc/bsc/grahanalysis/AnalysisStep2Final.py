#!/public/spark-0.9.1/bin/pyspark

import os
import sys
import csv

import datetime

import happybase
import numpy as np
from pynauty import *
import re
import networkx as nx
from hdfs import Config
from networkx.algorithms.approximation import maximum_independent_set, max_clique
from upc.bsc.Constants import SAMPLES, CHR_MAP, BANDWIDTH_CANDIDATES, THRESHOLD_COUNTERS, SAMPLE_CANCER


# Set the path for spark installation
# this is the path where you have built spark using sbt/sbt assembly
#os.environ['SPARK_HOME'] = "/usr/lib/spark"
# os.environ['SPARK_HOME'] = "/home/jie/d2/spark-0.9.1"
# Append to PYTHONPATH so that pyspark could be found
# from SubgraphCollection import SubgraphCollection
# from VsigramGraph import VsigramGraph

sys.path.append("/usr/lib/spark/python")
sys.path.append("/usr/lib/spark/python/lib/py4j-0.10.4-src.zip")
# sys.path.append("/home/jie/d2/spark-0.9.1/python")

# Now we are ready to import Spark Modules
try:
    from pyspark import SparkContext
    from pyspark import SparkConf

except ImportError as e:
    print ("Error importing Spark Modules", e)
    sys.exit(1)


def get_subgraph_hash(edges_indexes):
    # ORDER INSIDE EDGES IS ALREADY DONE
    # NOW ONLY NEED TO ORDER EDGES BETWEEN THEMSELVES
    hash_str = ''
    # rearrange the edges
    edges_indexes = sorted(edges_indexes)  # sorts on the first elements first and then on second
    for edge in edges_indexes:
        hash_str += str(edge) + ';'
    return hash_str


def map_to_tuple_with_hash(combination):
    # edges are list of indexes
    # this is going to be the key
    if type(combination) is int:
        combination = [combination]
    return (get_subgraph_hash(combination), combination)


def transform_to_original_edges(edges_indexes, positions_list):
    result_edges = list()
    for index in edges_indexes:
        result_edge = (positions_list[index[0]], positions_list[index[1]])
        result_edges.append(result_edge)
    return result_edges


def chr_str(chr_index):
    chrom_str = 'chr'
    if chr_index == 22:
        chrom_str += 'X'
    else:
        if chr_index == 23:
            chrom_str += 'Y'
        else:
            chrom_str += str(chr_index + 1)
    return chrom_str


def find_relative_position(position):
    # index = chr_number(chromosome)
    offset = 0L
    for i in range(len(CHR_MAP) + 1):
        if offset < position < offset + long(CHR_MAP[i]):
            chrom_str = chr_str(i)
            pos = position - offset
            # print 'RETURNING ' + str(chrom_str) + ' ' + str(pos)
            return chrom_str, pos
        else:
            offset += long(CHR_MAP[i])


def map_to_graph(combination_with_index, edges, positions_list):
    # edges are list of tuples

    # this is going to be the key
    # print combination_with_index
    combination = combination_with_index[0]
    # print 'comb: ' + str(combination)
    index = combination_with_index[1]
    # print 'index: ' + str(index)
    original_edges = list()
    if type(combination) is int:
        combination = [combination]
    for ind in combination:
        original_edges.append(edges.value[ind])
    original_vertices = set()
    for edge in original_edges:
        original_vertices.add(edge[0])
        original_vertices.add(edge[1])
    original_vertices = list(original_vertices)
    g = Graph(len(original_vertices))
    new_edges = list()
    for edge in original_edges:
        g.connect_vertex(original_vertices.index(edge[0]), original_vertices.index(edge[1]))
        new_edges.append((original_vertices.index(edge[0]), original_vertices.index(edge[1])))
    # check if the graph is from one chromosome or not
    original_graph = [transform_to_original_edges(original_edges, positions_list)]
    chromosomes = set()
    intra = False
    for orig_graph in original_graph:
        for orig_edge in orig_graph:
            for position in orig_edge:
                # print str(float(position))
                chrom, pos = find_relative_position(float(position))
                # print 'RETURNED ' + str(chrom) + ' ' + str(pos)
                chromosomes.add(chrom)
    if len(chromosomes) == 1:
        intra = True
    posting_list = dict()
    for edge in original_graph[0]:
        # print edge
        edge_hash = str(edge[0]) + ':' + str(edge[1])
        posting_list[edge_hash] = [index]

    return (canon_label(g), ((1, posting_list) if not intra else (0, dict()), (1, posting_list) if intra else (0, dict())))
    #return (canon_label(g), (1, [original_edges]))


def fix_frequency(pattern):
    graphs = pattern[1][1]
    nodes = range(len(graphs))
    nx_g = nx.Graph()
    nx_g.add_nodes_from(nodes)
    for index0 in range(len(graphs)):
        for index1 in range(index0 + 1, len(graphs)):
            # if two graphs under indexes have at least one edge in common - draw an edge
            graph0 = set(graphs[index0])
            graph1 = set(graphs[index1])
            intersection = graph0.intersection(graph1)
            if 0 < len(intersection):
                # build a edge
                nx_g.add_edge(index0, index1)
    graphs_connected = list(nx.connected_component_subgraphs(nx_g))
    freq = 0
    for graph in graphs_connected:
        freq += len(maximum_independent_set(graph))
    return (pattern[0], [pattern[1][0], freq, pattern[1][1]])


def update_subgraph_freq(a, b):
    # freq_object = SubgraphCollection(label=a.label)
    # freq_object.subgraphs = a.subgraphs + b.subgraphs
    # freq_object.freq = a.freq + b.freq
    posting_list_1_1 = a[0][1]
    posting_list_2_1 = b[0][1]
    # print '1_1 ' + str(posting_list_1_1)
    # print '2_1 ' + str(posting_list_2_1)

    for key in posting_list_2_1:
        if key not in posting_list_1_1:
            posting_list_1_1[key] = posting_list_2_1[key]
        else:
            posting_list_1_1[key].extend(posting_list_2_1[key])
    posting_list_1_2 = a[1][1]
    posting_list_2_2 = b[1][1]
    # print '1_2 ' + str(posting_list_1_2)
    # print '2_2 ' + str(posting_list_2_2)
    for key in posting_list_2_2:
        if key not in posting_list_1_2:
            posting_list_1_2[key] = posting_list_2_2[key]
        else:
            posting_list_1_2[key].extend(posting_list_2_2[key])
    return ((a[0][0]+ b[0][0], posting_list_1_1),(a[1][0]+ b[1][0], posting_list_1_2))


def filter_by_connected(edges_indexes, orig_edges):
    # create networkx graph
    first_element = True
    edge_new = edges_indexes[len(edges_indexes) - 1]
    edges_old = list(edges_indexes[0:len(edges_indexes) - 1]) if type(edges_indexes[0:len(edges_indexes) - 1]) is list \
        else [edges_indexes[0:len(edges_indexes) - 2]]
    # print str(edges_old) + str(type(edges_old))
    # print str(edge_new) + str(type(edge_new))
    if first_element:
        # print 'INDEXES: ' + str(edges_indexes) + str(type(edges_indexes))
        # print 'OLD: ' + str(edges_old) + str(type(edges_old))
        # print 'NEW: ' + str(edge_new) + str(type(edge_new))
        # print str(edge_new in edges_old)
        first_element = False
    if edge_new in edges_old:
        # print 'REPEATING EDGE'
        return False
    edges_list = list()
    for ind in list(edges_indexes):
        edges_list.append(orig_edges[ind])
    # print edges_list
    nx_g = nx.Graph()
    nx_g.add_edges_from(edges_list)
    return nx.is_connected(nx_g)


def map_to_list(edges_indexes):
    tupl_to_list = list(edges_indexes[0]) if type(edges_indexes[0]) is list else [edges_indexes[0]]
    tupl_to_list.append(edges_indexes[1])
    # print 'LIST: ' + str(tupl_to_list)
    return tupl_to_list


def join_connected_edges(combination, original_edges):
    edges_indexes_list = list(combination) if type(combination) is list else [combination]
    result_list = []
    combination_edges = []
    vertices_set = set()

    for edge_index in edges_indexes_list:
        edge_current = original_edges.value[edge_index]
        combination_edges.append(edge_current)
        vertices_set.add(edge_current[0])
        vertices_set.add(edge_current[1])

    for edge in original_edges.value:
        if edge not in combination_edges and (edge[0] in vertices_set or edge[1] in vertices_set):
            new_list = edges_indexes_list + [original_edges.value.index(edge)]
            # print new_list
            result_list.append(new_list)
    # print 'LISTS: ' + str(result_list)
    return result_list


def join_connected_edges_gen_parent(combination, original_edges):
    edges_indexes_list = list(combination) if type(combination) is list else [combination]
    result_list = []
    combination_edges = []
    vertices_set = set()


    for edge_index in edges_indexes_list:
        edge_current = original_edges.value[edge_index]
        combination_edges.append(edge_current)
        vertices_set.add(edge_current[0])
        vertices_set.add(edge_current[1])

    vertices_list = list(vertices_set)
    #parent canonical
    g = Graph(len(vertices_list))
    for edge in combination_edges:
        g.connect_vertex(vertices_list.index(edge[0]), vertices_list.index(edge[1]))
    c_parent = canon_label(g)

    for edge in original_edges.value:
        if edge not in combination_edges and (edge[0] in vertices_set or edge[1] in vertices_set):
            new_list = edges_indexes_list + [original_edges.value.index(edge)]
            new_edges = combination_edges + [edge]
            new_vertices = vertices_set.copy()
            new_vertices.add(edge[0])
            new_vertices.add(edge[1])
            new_vertices_list = list(new_vertices)
            g_child = Graph(len(new_vertices_list))
            for edge_child in new_edges:
                g_child.connect_vertex(new_vertices_list.index(edge_child[0]), new_vertices_list.index(edge_child[1]))
            c_child = canon_label(g_child)
            if generating_parent(c_child, c_parent):
                # print new_list
                result_list.append(new_list)
    # print 'LISTS: ' + str(result_list)
    return result_list



def find_generating_parent(c_child):
    edges = list()
    adj_elements = c_child[:-1].split(';')
    for adj_line in adj_elements:
        adj_line = adj_line.strip()
        edges_line = adj_line.split(':')
        out_edge = int(edges_line[0])
        in_edges = edges_line[1].strip().split(' ')
        for element in in_edges:
            in_edge = int(element)
            if (out_edge < in_edge) and ((out_edge, in_edge) not in edges):
                edges.append((out_edge, in_edge))
            else:
                if (in_edge, out_edge) not in edges:
                    edges.append((in_edge, out_edge))

    # deleting last edge
    orig_edges = list(edges)
    last_index = len(edges) - 1
    last_edge = orig_edges[last_index]
    while last_edge is not None:
        edges = list(orig_edges)
        edges.remove(last_edge)
        # create networkx graph
        nx_g = nx.Graph()
        nx_g.add_edges_from(edges)
        if not nx.is_connected(nx_g):
            last_index -= 1
            last_edge = orig_edges[last_index]
        else:
            last_edge = None
    # found good graph, now create the pynauty version
    vertices = set()
    for edge in edges:
        vertices.add(edge[0])
        vertices.add(edge[1])
    vertices_list = list(vertices)
    g = Graph(len(vertices_list))
    for edge in edges:
        g.connect_vertex(vertices_list.index(edge[0]), vertices_list.index(edge[1]))
    label = canon_label(g)
    return label.strip()


def generating_parent(c_child, c_parent):
    label = find_generating_parent(c_child)
    return label.strip() == c_parent.strip()


def save_to_hbase(record, bandwidth, threshold_counter, sample, size):
    connection = happybase.Connection(host='localhost')
    sample_pattern_table = connection.table('sample_pattern')
    # create row_key
    row_key = 'b' + str(int(bandwidth)) + 't' + str(threshold_counter) + 's' + sample + 'p' + record[0].strip()
    # collect values
    if size == 1:
        freq_inter_fixed = record[1][0][0]
        freq_intra_fixed = record[1][1][0]
    else:
        freq_inter_fixed = -1
        freq_intra_fixed = -1
    values = {b's:name': sample.encode('utf-8'), b's:cancer': SAMPLE_CANCER[sample].encode('utf-8'),
              b'p:code': record[0].strip().encode('utf-8'), b'p:size': str(size).encode('utf-8'),
              b'p:parent': '0' if size == 1 else find_generating_parent(record[0]).encode('utf-8'),
              b'b:value': str(int(bandwidth)).encode('utf-8'),
              b't:counter': str(threshold_counter).encode('utf-8'), b't:value': b'0.0',
              b'f:freq_inter': str(record[1][0][0]).encode('utf-8'), b'f:freq_intra': str(record[1][1][0]).encode('utf-8'),
              b'f:fix_freq_inter': str(freq_inter_fixed).encode('utf-8'), b'f:fix_freq_intra': str(freq_intra_fixed).encode('utf-8')}
    # embeddings
    inter_posting = record[1][0][1]
    for posting_key in inter_posting.keys():
        values[('e:inter_' + posting_key).encode('utf-8')] = str(inter_posting[posting_key]).encode('utf-8')
    intra_posting = record[1][1][1]
    for posting_key in intra_posting.keys():
        values[('e:intra_' + posting_key).encode('utf-8')] = str(intra_posting[posting_key]).encode('utf-8')
    # print values
    sample_pattern_table.put(row_key.encode('utf-8'), values)


hdfs_root = 'hdfs://localhost:54310/'
client = Config().get_client('dev')

conf = SparkConf().setAppName('SubgraphMining').setMaster('local[*]')
sc = SparkContext(conf=conf)

# load the edges and deduplicate them
# edges = map_csv_to_edges_list(path='/home/kkrasnas/Documents/thesis/pattern_mining/validation_data/new_assignment_separate.csv')

for bandwidth in BANDWIDTH_CANDIDATES:
    for sample in SAMPLES:
        for threshold_counter in THRESHOLD_COUNTERS:
            print 'BANDWIDTH ' + str(bandwidth) + ', THRESHOLD ' + str(threshold_counter) + ', SAMPLE ' + sample
            # try to read from hdfs
            client.delete('subgraphs/b' + str(int(bandwidth)) + '/' + sample + '/t' + str(threshold_counter), recursive=True)

            lines = sc.textFile(hdfs_root + 'samples/b' + str(int(bandwidth)) + '/' + sample
                                + '/t' + str(threshold_counter) + '/' + sample + '_new_assignment.csv')
            header = lines.first()  # extract header
            lines = lines.filter(lambda row: row != header)   # filter out header
            positions_rdd = lines.map(lambda line: line.split(','))
            # print positions_rdd.collect()
            positions_combined = lines.flatMap(lambda line: line.split(','))
            positions_distinct = positions_combined.distinct()
            positions_distinct_list = positions_distinct.collect()
            edges_rdd = positions_rdd.map(lambda positions: [positions_distinct_list.index(positions[0])
                                                             if positions_distinct_list.index(positions[0]) < positions_distinct_list.index(positions[1])
                                                             else positions_distinct_list.index(positions[1]),
                                                             positions_distinct_list.index(positions[1])
                                                             if positions_distinct_list.index(positions[0]) < positions_distinct_list.index(positions[1])
                                                             else positions_distinct_list.index(positions[0])])
            edges_rdd = edges_rdd.map(lambda edge: (str(edge[0]) + ':' + str(edge[1]), (edge, 1)))
            edges_rdd = edges_rdd.reduceByKey(lambda edge_kv1, edge_kv2: (edge_kv1[0], edge_kv1[1] + edge_kv2[1]) )
            edges_rdd_list = edges_rdd.collect()
            edges = [tuple(item[1][0]) for item in edges_rdd_list]
            edges_list = sc.broadcast(edges)

            rdd_1 = sc.parallelize(range(len(edges)))
            rdd_with_numbers_1 = rdd_1.zipWithIndex()
            # print rdd_with_numbers_1.collect()
            rdd_of_graphs_1 = rdd_with_numbers_1.map(lambda combination: map_to_graph(combination, edges_list, positions_distinct_list))
            counts_by_label_1 = rdd_of_graphs_1.reduceByKey(lambda a, b: update_subgraph_freq(a, b))
            #counts_by_label_1.saveAsTextFile(hdfs_root + 'subgraphs/b' + str(int(bandwidth)) + '/' + sample
             #                                  + '/t' + str(threshold_counter) + '/' + str(1))
            counts_by_label_1.foreach(lambda record: save_to_hbase(record, bandwidth, threshold_counter, sample, 1))
            rdd_last = rdd_1

            for i in range(2, 5):
                print 'SIZE ' + str(i)
                # for each element in rdd_1 create a list and add to new rdd
                rdd_next = rdd_last.flatMap(lambda combination: join_connected_edges_gen_parent(combination, edges_list))
                rdd_next = rdd_next.map(lambda combination: map_to_tuple_with_hash(combination))
                # print rdd_next.first()
                print 'Before deduplication ' + str(rdd_next.count())
                rdd_next = rdd_next.reduceByKey(lambda a, b: a)
                print 'After deduplication ' + str(rdd_next.count())
                rdd_next = rdd_next.map(lambda x: x[1])
                rdd_last = rdd_next
                # create a graph from each list
                rdd_next_with_index = rdd_next.zipWithIndex()
                rdd_of_graphs = rdd_next_with_index.map(lambda combination: map_to_graph(combination, edges_list, positions_distinct_list))
                # print rdd_of_graphs.first()
                counts_by_label = rdd_of_graphs.reduceByKey(lambda a, b: update_subgraph_freq(a, b))
                #print counts_by_label.first()
                # fix the frequency
                #fixed_freq = counts_by_label.map(lambda pattern: fix_frequency(pattern))
                counts_by_label.saveAsTextFile(hdfs_root + 'subgraphs/b' + str(int(bandwidth)) + '/' + sample
                                               + '/t' + str(threshold_counter) + '/' + str(i))
                counts_by_label.foreach(lambda record: save_to_hbase(record, bandwidth, threshold_counter, sample, i))
