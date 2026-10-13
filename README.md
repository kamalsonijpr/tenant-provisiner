# tenant-provisiner

## Messaging and concurrency demos

Run the concurrency check against a live API:

```bash
python scripts/concurrency_check.py --base-url http://localhost:8000 --slug race-demo --name "Race Demo" --version 1
```

Publish a manual worker progress event to RabbitMQ for negative-scenario demos:

```bash
python scripts/publish_progress.py \
  --task-id <tenant-task-uuid> \
  --status in_progress \
  --worker-id demo-worker \
  --idempotency-key stale-progress \
  --rabbitmq-url amqp://guest:guest@localhost:5672/
```

The first script sends two PATCH requests with the same version to confirm only one can win.
The second script publishes a worker update directly to the task.progress exchange so stale or duplicate deliveries can be exercised without the full worker simulator.
