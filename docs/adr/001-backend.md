# ADR-001: Modular Python core with independent API and worker

Status: accepted for foundation. Context: four-person product team, local laptop and eventual municipal deployment.

Decision: one typed domain package, separate FastAPI and worker processes, React and Android apps in monorepo. Requirements FUNC-014, EXT-018.

Alternatives: separate service for every AI stage increases operational burden; synchronous request inference couples availability to models.

Consequences: shared contracts and simple local execution; worker can scale independently. Package boundaries enforce vendor adapters, not empty microservices. Model failure leaves original case reviewable. API must never import dispatch into model pipeline. Split services only after measured independent scaling needs.
