// SPDX-License-Identifier: GPL-3.0-only

#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#include <assert.h>
#include <endian.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>

#include <blkid/blkid.h>
#include <libdevmapper.h>
#include <sha2.h>

#include "metadata_format.h"

#define LINEAR_PARAMS_SIZE 256

static const uint8_t zero[32] = {
	0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
};

/*
 * Part 1:
 *
 * The following functions are for struct validation. They do simple
 * comparisons and checksums. If they fail, they output an error and
 * return NULL. They take the struct as a parameter, and sometimes a
 * scope (TODO: improve the error messages).
 */

LpMetadataGeometry *validateMetadataGeometry(LpMetadataGeometry *geom, const char *scope) {
	SHA2_CTX sha2;
	uint8_t checksum[SHA256_DIGEST_LENGTH];

	if (le32toh(geom->magic) != LP_METADATA_GEOMETRY_MAGIC) {
		fprintf(stderr, "%s: Invalid metadata geometry magic number (expected 0x%X, got 0x%X)\n", scope, LP_METADATA_GEOMETRY_MAGIC, le32toh(geom->magic));
		return NULL;
	}

	if (le32toh(geom->struct_size) != sizeof(LpMetadataGeometry)) {
		fprintf(stderr, "%s: Invalid geometry size\n", scope);
		return NULL;
	}

	// Calculate the checksum if the checksum field was zero
	SHA256Init(&sha2);
	SHA256Update(&sha2, (const uint8_t *) geom, offsetof(LpMetadataGeometry, checksum));
	SHA256Update(&sha2, zero, 32);
	SHA256Update(&sha2, &geom->checksum[32], geom->struct_size - offsetof(LpMetadataGeometry, checksum) - 32);
	SHA256Final(checksum, &sha2);

	if (memcmp(checksum, geom->checksum, SHA256_DIGEST_LENGTH)) {
		fprintf(stderr, "%s: Metadata geometry integrity check failed\n", scope);
		return NULL;
	}

	if (le32toh(geom->metadata_max_size) % LP_SECTOR_SIZE) {
		fprintf(stderr, "%s: Invalid metadata header maximum size\n", scope);
		return NULL;
	}

	if (le32toh(geom->metadata_slot_count) > 3 || le32toh(geom->metadata_slot_count) < 1) {
		fprintf(stderr, "%s: Unknown number of slots %u\n", scope, le32toh(geom->metadata_slot_count));
		return NULL;
	}

	return geom;
}

LpMetadataHeader *validateMetadataHeader(LpMetadataHeader *header, const char *scope) {
	SHA2_CTX sha2;
	uint8_t checksum[SHA256_DIGEST_LENGTH];

	if (le32toh(header->magic) != LP_METADATA_HEADER_MAGIC) {
		fprintf(stderr, "%s: Invalid magic number for the metadata header (expected 0x%X, got 0x%X)\n", scope, LP_METADATA_HEADER_MAGIC, le32toh(header->magic));
		return NULL;
	}

	if (le32toh(header->major_version) != LP_METADATA_MAJOR_VERSION
#if LP_METADATA_MINOR_VERSION_MIN // The compiler complains when this condition is always false
	 || le32toh(header->minor_version) < LP_METADATA_MINOR_VERSION_MIN
#endif
	 || le32toh(header->minor_version) > LP_METADATA_MINOR_VERSION_MAX) {
		fprintf(stderr, "%s: Unsupported header version %u.%u\n", scope, le32toh(header->major_version), le32toh(header->minor_version));
		return NULL;
	}

	if (le32toh(header->minor_version) == 0 && le32toh(header->header_size) != sizeof(LpMetadataHeaderV1_0)) {
		fprintf(stderr, "%s: Invalid size for metadata header v10.0\n", scope);
		return NULL;
	}

	if (le32toh(header->minor_version) == 2 && le32toh(header->header_size) != sizeof(LpMetadataHeaderV1_2)) {
		fprintf(stderr, "%s: Invalid size for metadata header v10.2\n", scope);
		return NULL;
	}

	// Calculate the checksum if the checksum field was zero
	SHA256Init(&sha2);
	SHA256Update(&sha2, (const uint8_t *) header, offsetof(LpMetadataHeader, header_checksum));
	SHA256Update(&sha2, zero, 32);
	SHA256Update(&sha2, &header->header_checksum[32], header->header_size - offsetof(LpMetadataHeader, header_checksum) - 32);
	SHA256Final(checksum, &sha2);

	if (memcmp(checksum, header->header_checksum, SHA256_DIGEST_LENGTH)) {
		fprintf(stderr, "%s: Metadata header integrity check failed\n", scope);
		return NULL;
	}

	if (le32toh(header->tables_size) != le32toh(header->partitions.entry_size) * le32toh(header->partitions.num_entries) + le32toh(header->extents.entry_size) * le32toh(header->extents.num_entries) + le32toh(header->groups.entry_size) * le32toh(header->groups.num_entries) + le32toh(header->block_devices.entry_size) * le32toh(header->block_devices.num_entries)) {
		fprintf(stderr, "%s: Invalid metadata tables size\n", scope);
		return NULL;
	}

	SHA256Init(&sha2);
	SHA256Update(&sha2, (const void *) &((const uint8_t *) header)[le32toh(header->header_size)], le32toh(header->tables_size));
	SHA256Final(checksum, &sha2);

	if (memcmp(checksum, header->tables_checksum, SHA256_DIGEST_LENGTH)) {
		fprintf(stderr, "%s: Metadata tables integrity check failed\n", scope);
		return NULL;
	}

	return header;
}

/*
 * Part 2:
 *
 * This function takes in an array of block devices (blockDevs) and
 * resolves them according to their partition label, storing the
 * results in blockDevicePaths. It is sometimes necessary to
 * append/suffix the slot identifier (slotId).
 *
 * The resulting strings are newly allocated by libblkid, and should be
 * freed.
 */

void resolveBlockDevices(const LpMetadataBlockDevice *blockDevs, char **blockDevicePaths, uint32_t blockDeviceCount, const char *slotId) {
	char buf[39];

	for (unsigned i = 0; i < blockDeviceCount; i++) {
		// Prevent out of bounds memory access when concatenating strings
		strncpy(buf, blockDevs[i].partition_name, 36);
		buf[37] = '\0';
		
		if (le32toh(blockDevs[i].flags) & LP_BLOCK_DEVICE_SLOT_SUFFIXED)
			strcat(buf, slotId);

		blockDevicePaths[i] = blkid_evaluate_tag("PARTLABEL", buf, NULL);
	}
}

/*
 * Part 3:
 *
 * These functions do the actual mapping. They take in the partitions
 * extents they reference, and block devices which they use, and pass
 * the partitions to the device mapper. The functions are separate to
 * avoid excessive indentation.
 *
 * There are some error messages here for when the mappings cannot be
 * made.
 */

uint64_t addExtentAsTarget(struct dm_task *dmt, LpMetadataExtent *extent, uint32_t sector, const char **blockDevices, const char *scope) {
	char buf[LINEAR_PARAMS_SIZE];

	if (le32toh(extent->target_type) == LP_TARGET_TYPE_LINEAR && blockDevices[le32toh(extent->target_source)]) {
		snprintf(buf, LINEAR_PARAMS_SIZE, "%s %llu", blockDevices[le32toh(extent->target_source)], (long long unsigned int) le64toh(extent->target_data));
		dm_task_add_target(dmt, sector, le64toh(extent->num_sectors), "linear", buf);
	} else if (le32toh(extent->target_type) == LP_TARGET_TYPE_ZERO)
		dm_task_add_target(dmt, sector, le64toh(extent->num_sectors), "zero", "");
	else {
		if (le32toh(extent->target_type) == LP_TARGET_TYPE_LINEAR)
			fprintf(stderr, "%s: Unresolved block device, punching hole\n", scope);
		else
			fprintf(stderr, "%s: Unknown device mapper entry type %u, punching hole\n", scope, le32toh(extent->target_source));

		dm_task_add_target(dmt, sector, le64toh(extent->num_sectors), "error", "");
	}

	return le64toh(extent->num_sectors);
}

void writeMappingsFromMetadata(LpMetadataHeader *header, LpMetadataPartition *parts, LpMetadataExtent *extents, const char **blockDevices, const char *slotId) {
	uint32_t sector;

	struct dm_task *dmt;

	char buf[39];

	for (uint32_t i = 0; i < le32toh(header->partitions.num_entries); i++) {
		// Extent index bounds check
		if (le32toh(parts[i].first_extent_index) + le32toh(parts[i].num_extents) > le32toh(header->extents.num_entries)) {
			fprintf(stderr, "%.36s%s: partition extents extend past the extent table\n", parts[i].name, slotId);
			break;
		}

		dmt = dm_task_create(DM_DEVICE_CREATE);

		// Prevent out of bounds memory access when concatenating strings
		strncpy(buf, parts[i].name, 36);
		buf[37] = '\0';

		if (parts[i].attributes & LP_PARTITION_ATTR_SLOT_SUFFIXED)
			strcat(buf, slotId);

		dm_task_set_name(dmt, buf);

		sector = 0;
		for (uint32_t j = 0; j < le32toh(parts[i].num_extents); j++)
			sector += addExtentAsTarget(dmt, &extents[j + le32toh(parts[i].first_extent_index)], sector, blockDevices, buf);

		dm_task_run(dmt);
		dm_task_destroy(dmt);
	}
}

int main(int argc, char **argv) {
	char *superPartition;

	int fd;

	LpMetadataGeometry *geom;
	LpMetadataHeader *header;
	LpMetadataPartition *parts;
	LpMetadataExtent *extents;
	LpMetadataBlockDevice *physPart;

	char **blockDevicePaths;

	int slotN = 0;

	static const char *slotIds[] = {
		"_a",
		"_b",
		"_c"
	};

	if (argc < 2) {
		fprintf(stderr, "Usage: %s SUPER_PARTITION [SLOT_NUMBER [BLOCK_DEVICES]]\n", argv[0]);
		return 1;
	}

	superPartition = blkid_evaluate_spec(argv[1], NULL);
	if (!superPartition) {
		fprintf(stderr, "Could not find block device \"%s\"\n", argv[1]);
		return 1;
	}

	fd = open(superPartition, O_RDONLY);
	if (fd == -1) {
		fprintf(stderr, "Could not open %s: %s\n", argv[1], strerror(errno));
		return 1;
	}

	if (argc >= 3)
		slotN = strtol(argv[2], NULL, 0);

	geom = malloc(LP_METADATA_GEOMETRY_SIZE * 2);

	// Seek to the beginning of the metadata
	lseek(fd, LP_PARTITION_RESERVED_BYTES, SEEK_SET);

	// Find first valid geometry struct
	read(fd, geom, LP_METADATA_GEOMETRY_SIZE);
	if (validateMetadataGeometry(geom, argv[1]))
		lseek(fd, LP_METADATA_GEOMETRY_SIZE, SEEK_CUR);
	else
		read(fd, geom, LP_METADATA_GEOMETRY_SIZE);

	if (validateMetadataGeometry(geom, argv[1]) == NULL) {
		fprintf(stderr, "No valid metadata geometry found\n");
		return 1;
	}

	header = malloc(le32toh(geom->metadata_max_size));

	// Skip the main and backup metadata of each slot before the requested one
	lseek(fd, le32toh(geom->metadata_max_size) * slotN * 2, SEEK_CUR);

	for (uint32_t i = slotN; i < le32toh(geom->metadata_slot_count); i++) {
		// Find the first valid metadata header struct
		read(fd, header, le32toh(geom->metadata_max_size));
		if (validateMetadataHeader(header, argv[1]))
			lseek(fd, le32toh(geom->metadata_max_size), SEEK_CUR);
		else
			read(fd, header, le32toh(geom->metadata_max_size));

		if (validateMetadataHeader(header, argv[1]) == NULL) {
			fprintf(stderr, "No valid metadata header found\n");
			goto next;
		}

		parts = (LpMetadataPartition *) &((uint8_t *) header)[le32toh(header->header_size) + le32toh(header->partitions.offset)];
		extents = (LpMetadataExtent *) &((uint8_t *) header)[le32toh(header->header_size) + le32toh(header->extents.offset)];
		physPart = (LpMetadataBlockDevice *) &((uint8_t *) header)[le32toh(header->header_size) + le32toh(header->block_devices.offset)];

#ifdef USERSPACE
		blockDevicePaths = calloc(le32toh(header->block_devices.num_entries), sizeof(char *));
		blockDevicePaths[0] = superPartition;
		for (int j = 1; j + 2 < argc && j < le32toh(header->block_devices.num_entries); j++)
			blockDevicePaths[j] = argv[j + 2];
#else
		blockDevicePaths = malloc(sizeof(char *) * le32toh(header->block_devices.num_entries));
		resolveBlockDevices(physPart, blockDevicePaths, le32toh(header->block_devices.num_entries), slotIds[i]);
#endif

		writeMappingsFromMetadata(header, parts, extents, (const char **) blockDevicePaths, slotIds[i]);

#ifndef USERSPACE
		for (unsigned j = 0; j < le32toh(header->block_devices.num_entries); j++)
			free(blockDevicePaths[j]);
#endif
		free(blockDevicePaths);

	next:
		// If the user specified a slot, then only that slot should be processed
		if (argc >= 3)
			break;

		// Fix for google-sargo (it has 2 super partitions, each with 2 slots with the same logical partitions)
		if (!(le32toh(physPart->flags) & LP_BLOCK_DEVICE_SLOT_SUFFIXED)) {
			fprintf(stderr, "warn: This looks like metadata for retrofit partitions. Only the first slot is mapped.\n");
			break;
		}
	}

	free(header);
	free(geom);
	free(superPartition);

	return 0;
}
