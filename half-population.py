from __future__ import division
import sys
import fiona
import argparse
import shapely.geometry

def parse_args(argv):
    parser = argparse.ArgumentParser(description='')
    parser.add_argument("-i", "--input")
    parser.add_argument("-o", "--output")
    parser.add_argument("-p", "--property-to-half")
    parser.add_argument("-c", "--output-column", default="half")

    args = parser.parse_args(argv)

    return args


def open_input_source(filename):
    results = []
    with fiona.open(filename) as source:
        for record in source:
            results.append(record)
        meta = source.meta

    return results, meta

def write_shapefile(filename, objects, metadata):
    with fiona.open(filename, 'w', driver=metadata['driver'], crs=metadata['crs'], schema=metadata['schema']) as output:
        for obj in objects:
            output.write(obj)


def add_output_column(shapes, fileformat_meta, column_name):
    if column_name in fileformat_meta['schema']['properties']:
        raise ValueError()

    fileformat_meta['schema']['properties'][column_name] = 'int'

    for shape in shapes:
        shape['properties'][column_name] = 0

    return shapes, fileformat_meta

def allocate_shapes(shapes, input_column_name, output_column_name):
    shapes_by_id = {shape['id']: shape for shape in shapes}
    areas = {shape['id']: shapely.geometry.shape(shape['geometry']).area for shape in shapes}
    densities = {shape['id']: shape['properties'][input_column_name] / areas[shape['id']] for shape in shapes}
    total = sum(shape['properties'][input_column_name] for shape in shapes)
    assert total > 0
    half = total / 2
    so_far = 0
    first_half_ids = set()

    for shape in sorted(shapes, key=lambda shape: (shape['properties'][input_column_name] / shapely.geometry.shape(shape['geometry']).area) ):
        # would including this item put us over half way point?
        this_value = shape['properties'][input_column_name]
        if so_far + this_value == half:
            # include this item, then stop
            so_far += shape['properties'][input_column_name]
            shape['properties'][output_column_name] = 1
            break
        elif so_far + this_value > half:
            # So this is the last item we look at. We should assign it to the
            # first half if it would result in less of a difference from the
            # target half way
            if (so_far + this_value) - half < half - so_far:
                # If we include this item, we'll be closer to the target
                # halfway point than if we don't. So include it
                so_far += shape['properties'][input_column_name]
                shape['properties'][output_column_name] = 1

            # But regardless, we should stop now.
            break
        elif so_far + this_value < half:
            # Still a good bit to go, so assign this shape to this half
            so_far += shape['properties'][input_column_name]
            shape['properties'][output_column_name] = 1
        else:
            raise NotImplementedError("Impossible code path")

    return shapes, total, so_far

def print_result_stats(total, first_half):
    second_half = total - first_half
    print "There is {:,} in total, and {:,} ({:5.2%}) in first half, {:,} ({:5.2%}) in second half".format(total, first_half, first_half/total, second_half, second_half/total)


def main(argv):
    args = parse_args(argv)
    shapes, fileformat_meta = open_input_source(args.input)
    shapes, fileformat_meta = add_output_column(shapes, fileformat_meta, args.output_column)
    shapes, total, first_half = allocate_shapes(shapes, args.property_to_half, args.output_column)
    print_result_stats(total, first_half)
    write_shapefile(args.output, shapes, fileformat_meta)

if __name__ == '__main__':
    main(sys.argv[1:])
