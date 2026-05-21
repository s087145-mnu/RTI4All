# Data Persistence in RTI4All

## Overview

The RTI4All backend now includes a robust data persistence layer that automatically saves all changes to disk. This ensures that:

- New RTI requests are immediately saved
- Admin updates to requests are persisted
- Data survives container restarts
- Automatic backups are created before modifications
- Error recovery from corrupted files is possible

## Features

### Automatic Persistence

All data modifications (creating requests, updating statuses, etc.) are automatically saved to disk using atomic writes to prevent data corruption.

### Automatic Backups

Before each save operation, the system creates a timestamped backup in `backend/data/backups/`. The system retains the most recent backups and automatically cleans up old ones.

### Error Handling

The persistence layer includes comprehensive error handling:

- **Corrupted data file**: Automatically recovers from the most recent valid backup
- **Failed writes**: Logs errors but doesn't fail the request (data remains in memory)
- **Missing files**: Falls back to direct file loading if persistence layer fails

### Atomic Writes

All save operations use atomic writes (write to temporary file, then rename) to ensure data integrity even if the process is interrupted.

## Configuration

### Environment Variables

- `ENABLE_DATA_PERSISTENCE` (default: `true`): Set to `false` to disable persistence
- `MAX_BACKUPS` (default: `10`): Maximum number of automatic backups to retain

### Example `.env` Configuration

```env
# Enable/disable data persistence
ENABLE_DATA_PERSISTENCE=true

# Maximum backups to keep (older backups are automatically deleted)
MAX_BACKUPS=10
```

## File Structure

```
backend/
├── data/
│   ├── sample_data.json          # Main data file
│   └── backups/                   # Automatic backups
│       ├── sample_data_20240320_143022.json
│       ├── sample_data_20240320_143445.json
│       └── checkpoint_demo_ready_20240320_150000.json
└── persistence.py                 # Persistence layer implementation
```

## Usage

### Automatic Persistence

No code changes needed! The system automatically persists data when:

1. A citizen creates a new RTI request
2. An admin updates a request status or response
3. An admin approves or rejects a draft response

### Manual Checkpoints

You can create named checkpoints (manual backups) programmatically:

```python
from main import _data_store

if _data_store:
    _data_store.create_checkpoint("before_demo")
```

### Recovery from Backup

If the main data file becomes corrupted, the system automatically tries to recover from the most recent valid backup. Manual recovery:

```bash
# List available backups
ls -lh backend/data/backups/

# Manually restore from a specific backup
cp backend/data/backups/sample_data_20240320_143022.json backend/data/sample_data.json

# Restart the backend
docker compose restart backend
```

## Enhanced Sample Data

The system now includes comprehensive sample data across multiple departments:

- **5 departments**: Climate Change, Health, Education, Transport, Foreign Affairs
- **18 sample requests** with various statuses (Pending, In Progress, Under Review, Responded)
- **10 FAQs** covering common RTI questions
- Rich metadata including citizen contact information for demonstration purposes

## Testing

### Verify Persistence is Working

1. **Start the backend**:
   ```bash
   docker compose up backend
   ```

2. **Check startup logs**:
   ```
   [startup] ✓ Loaded 18 requests, 5 departments, 10 FAQs.
   RAG index: 12 items. Graph: 85 nodes. Persistence: enabled
   ```

3. **Create a test request** via the UI or API

4. **Check the data file**:
   ```bash
   cat backend/data/sample_data.json | jq '.requests | length'
   ```

5. **Verify backup was created**:
   ```bash
   ls -lh backend/data/backups/
   ```

### Test Error Recovery

1. **Corrupt the data file**:
   ```bash
   echo "{invalid json" > backend/data/sample_data.json
   ```

2. **Restart backend**:
   ```bash
   docker compose restart backend
   ```

3. **Check logs** - should show automatic recovery:
   ```
   [ERROR] JSON decode error in sample_data.json
   [WARNING] Recovered data from backup after JSON decode error
   [INFO] Data loaded successfully: 18 requests, 5 departments
   ```

## RAG Pipeline Benefits

With the expanded sample data, the RAG (Retrieval-Augmented Generation) pipeline now has:

- **More training data**: 12 responded requests indexed for similarity search
- **Cross-department knowledge**: Examples from multiple government ministries
- **Varied response patterns**: Different types of information disclosure scenarios
- **Better context matching**: More examples help the AI find relevant precedents

### Example RAG Query Flow

1. **Citizen asks about vaccination data**
2. **System searches vector index** for similar past requests
3. **Finds relevant match**: RTI-2024-0007 (COVID-19 vaccination statistics)
4. **Uses response as template** to draft a contextually appropriate answer
5. **Admin reviews and approves** the AI-generated draft

## Monitoring

### Check Persistence Status

```bash
# View backend logs
docker compose logs backend | grep -i persist

# Expected output:
# [INFO] DataStore initialized: file=.../sample_data.json, backups=enabled
# [INFO] Data loaded via persistence layer
# [DEBUG] Data persisted to disk
```

### Monitor Disk Usage

```bash
# Check data directory size
du -sh backend/data/

# Check number of backups
ls backend/data/backups/ | wc -l
```

## Production Considerations

1. **Backup retention**: Adjust `MAX_BACKUPS` based on your change frequency
2. **Disk space**: Monitor the backups directory, especially with high request volumes
3. **Performance**: The atomic write approach adds ~10-50ms per save operation
4. **Database migration**: For production, consider migrating to PostgreSQL or similar
5. **Backup strategy**: Set up external backups beyond the automatic local backups

## Troubleshooting

### Persistence Not Working

```bash
# Check if persistence is enabled
docker compose exec backend env | grep ENABLE_DATA_PERSISTENCE

# Check file permissions
ls -la backend/data/

# Ensure the backend can write to the data directory
docker compose exec backend touch backend/data/test.txt
```

### Data Not Saving

Check logs for errors:

```bash
docker compose logs backend | grep -i "failed to persist"
```

Common causes:
- Read-only file system
- Insufficient disk space
- File permission issues

### Backups Not Created

```bash
# Check backups directory exists
ls -la backend/data/backups/

# Check logs
docker compose logs backend | grep -i backup
```

## API Error Responses

The system now includes comprehensive error handling. Common error scenarios:

### Request Creation Failures

```json
{
  "detail": "Department 'invalid-dept' not found."
}
```

### Persistence Failures

If persistence fails, the request still succeeds (data remains in memory) but a warning is logged:

```
[ERROR] Failed to persist after creating request: [error details]
```

The response is still returned successfully to the client.

### AI Generation Failures

If AI answer generation fails, the request is filed as "Pending":

```json
{
  "id": "RTI-2024-0019",
  "status": "Pending",
  "response": null,
  ...
}
```

Admins can manually respond via the admin panel.

## Future Enhancements

Potential improvements for production deployments:

1. **Database backend**: Migrate from JSON to PostgreSQL
2. **Cloud storage**: Store backups in S3/Azure Blob/GCS
3. **Async persistence**: Move saves to background tasks
4. **Audit logging**: Track all data modifications with timestamps
5. **Replication**: Multi-node setup with data replication
6. **Versioning**: Track full history of request changes

## Support

For issues related to data persistence:

1. Check the logs: `docker compose logs backend`
2. Verify file permissions on `backend/data/`
3. Ensure sufficient disk space
4. Review the environment variables in `.env`
5. Try disabling persistence temporarily: `ENABLE_DATA_PERSISTENCE=false`
