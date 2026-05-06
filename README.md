# ppaa-e-approval-backend
#COMMAND TO back specific db 
docker exec -t postgres pg_dump -U postgres ppaa_internal_portal > backup.sql
or
docker exec -t postgres pg_dump -U postgres ppaa_internal_portal > ~/Desktop/backup.sql
