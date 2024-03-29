#!/public/spark-0.9.1/bin/pyspark

import os
import sys
import csv
import itertools
import numpy as np
from pynauty import *
import re
import networkx as nx


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
    from pyspark import SparkConf
    from pyspark import SparkContext
    from pyspark.sql import SparkSession
    from pyspark.sql.types import StructType
    from pyspark.sql.types import StructField
    from pyspark.sql.types import IntegerType
    from pyspark.sql.types import LongType
    from pyspark.sql.types import StringType
    from pyspark.sql.types import ArrayType


except ImportError as e:
    print ("Error importing Spark Modules", e)
    sys.exit(1)


def combinations_local(iterable, r):
    # combinations('ABCD', 2) --> AB AC AD BC BD CD
    # combinations(range(4), 3) --> 012 013 023 123
    pool = tuple(iterable)
    n = len(pool)
    if r > n:
        return
    indices = range(r)
    yield tuple(pool[i] for i in indices)
    while True:
        for i in reversed(range(r)):
            if indices[i] != i + n - r:
                break
        else:
            return
        indices[i] += 1
        for j in range(i+1, r):
            indices[j] = indices[j-1] + 1
        yield tuple(pool[i] for i in indices)


def map_csv_to_edges_list(path='/home/kkrasnas/Documents/thesis/pattern_mining/validation_data/new_assignment.csv'):
    with open(path, 'rb') as csvfile:
        reader = csv.DictReader(csvfile, fieldnames=['pos_1', 'pos_2'])
        next(csvfile)
        positions = list()
        edges_set = set()
        edges = list()
        for row in reader:
            positions.append((row['pos_1'], row['pos_2']))

        vertices_set = set()
        for position in positions:
            vertices_set.add(position[0])
            vertices_set.add(position[1])
        vertices_list = list(vertices_set)
        g = Graph(len(vertices_list))

        # ORIGINAL EDGES ARE ALL SORTED MIN -> MAX
        for edge in positions:
            # always minIndex -> maxIndex to avoid duplicate edges
            if vertices_list.index(edge[0]) < vertices_list.index(edge[1]):
                g.connect_vertex(vertices_list.index(edge[0]), vertices_list.index(edge[1]))
                edges_set.add((vertices_list.index(edge[0]), vertices_list.index(edge[1])))
            else:
                g.connect_vertex(vertices_list.index(edge[1]), vertices_list.index(edge[0]))
                edges_set.add((vertices_list.index(edge[1]), vertices_list.index(edge[0])))
        edges = list(edges_set)
        return edges


def map_to_graph(combination, edges):
    # edges are list of tuples

    # this is going to be the key
    original_edges = list()
    if type(combination) is int:
        combination = [combination]
    for ind in combination:
        original_edges.append(edges[ind])
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
    # v_g = VsigramGraph(g, None, label_arr=canon_label(g), orig_edges=original_edges)
    # subgraph_collection = SubgraphCollection(v_g.label_arr, subgraphs=[v_g], freq=1)
    return (canon_label(g), (1, [original_edges]))


def update_subgraph_freq(a, b):
    # freq_object = SubgraphCollection(label=a.label)
    # freq_object.subgraphs = a.subgraphs + b.subgraphs
    # freq_object.freq = a.freq + b.freq
    return (a[0] + b[0], a[1] + b[1])


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


def mapToList(edges_indexes):
    tupl_to_list = list(edges_indexes[0]) if type(edges_indexes[0]) is list else [edges_indexes[0]]
    tupl_to_list.append(edges_indexes[1])
    # print 'LIST: ' + str(tupl_to_list)
    return tupl_to_list




conf = SparkConf().setAppName('SubgraphMining').setMaster('local[*]')
sc = SparkContext(conf=conf)
ss = SparkSession \
    .builder \
    .appName("SubgraphMiningDF") \
    .getOrCreate()

# load the edges and deduplicate them
edges = map_csv_to_edges_list(path='/home/kkrasnas/Documents/thesis/pattern_mining/validation_data/new_assignment_separate.csv')
sample = '7d734d06-f2b1-4924-a201-620ac8084c49'
list_of_list = []
for edge in edges:
    list_of_list.append([edge])
rdd_1 = sc.parallelize(list_of_list)
print rdd_1.collect()
schema = StructType([StructField('c' + str(i), ArrayType(IntegerType()), True) for i in range(1)])
rdd_1_df = ss.createDataFrame(rdd_1, schema)
rdd_1_df.printSchema()
print rdd_1_df.schema.names
rdd_1_df.show()
# rdd_of_graphs_1 = rdd_1.map(lambda combination: map_to_graph(combination, edges))
# # rdd_filtered = rdd_of_graphs.filter(lambda x: x[1] is not None)
# counts_by_label_1 = rdd_of_graphs_1.reduceByKey(lambda a, b: update_subgraph_freq(a, b))
# print counts_by_label_1.collect()
# # counts_by_label_1.saveAsTextFile('hdfs://localhost:54310/subgraphs/' + sample + '/' + str(1))
dfs = list()
dfs.append(rdd_1_df)

for i in range(2, 3):
    print 'SIZE ' + str(i)
    # for each element in rdd_1 create a list and add to new rdd
    df_last = dfs[len(dfs) - 1]
    df_next = df_last.join(rdd_1_df, rdd_1_df.c0.contains(df_last.c0))  # and (() or ()))
    df_next.show()
#     rdd_next = df_next.rdd
#     print rdd_next.first()
#     # rdd_next = rdd_next.flatMap(lambda x: [element for tupl in x for element in tupl])
#     # filter the connected graphs
#     rdd_next = rdd_next.map(lambda x: mapToList(x))
#     rdd_next = rdd_next.filter(lambda comb: filter_by_connected(comb, edges))
#
#     print rdd_next.first()
#     dfs.append(rdd_next)
#     # create a graph from each list
#     rdd_of_graphs = rdd_next.map(lambda combination: map_to_graph(combination, edges))
# #     rdd_filtered = rdd_of_graphs.filter(lambda x: x[1] is not None)
#     counts_by_label = rdd_of_graphs.reduceByKey(lambda a, b: update_subgraph_freq(a, b))
#     counts_by_label.saveAsTextFile('hdfs://localhost:54310/subgraphs/' + sample + '/' + str(i))
